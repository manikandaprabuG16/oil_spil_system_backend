"""
AIS & Spill Trajectory Correlation Engine
------------------------------------------
Performs geometric and temporal intersection between:
1. Spatio-temporal vessel tracks
2. Hydrodynamically backtracked spill discharge cones
Calculates:
- Closest Point of Approach (CPA) to the backtracked origin
- Time delta at CPA
- Intersection with spill polygon boundary
- Speed & heading anomaly metrics
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import math
from shapely.geometry import Point, LineString, Polygon
from .ais_engine import parse_timestamp, haversine_distance_km


class CorrelationEngine:
    def __init__(self):
        pass

    def correlate_vessel_with_spill(
        self,
        vessel: Dict[str, Any],
        spill_centroid: Dict[str, float],
        spill_polygon_coords: Optional[List[List[float]]],
        backtrack_points: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyzes a single vessel against both the detection boundary and backtracked spill timeline.
        """
        track = vessel.get("filtered_track", vessel.get("track", []))
        if not track:
            return {
                "mmsi": vessel.get("mmsi"),
                "cpa_km": 999.0,
                "cpa_time": None,
                "spill_intersected": False,
                "speed_anomaly": False,
                "details": "No track points in window"
            }

        # Build Shapely polygon for the spill if available
        spill_poly = None
        if spill_polygon_coords and len(spill_polygon_coords) >= 3:
            try:
                spill_poly = Polygon(spill_polygon_coords)
            except Exception:
                spill_poly = None

        min_cpa_km = float("inf")
        best_vessel_ping = None
        best_backtrack_point = None
        intersected = False

        # Build a lookup of backtrack points sorted by timestamp
        bt_with_dt = []
        for bp in backtrack_points:
            try:
                bt_with_dt.append((parse_timestamp(bp["timestamp"]), bp))
            except Exception:
                continue

        # Evaluate every vessel ping against the time-closest backtrack position
        for ping in track:
            try:
                ping_dt = parse_timestamp(ping["timestamp"])
            except Exception:
                continue

            ping_lat = ping["lat"]
            ping_lon = ping["lon"]

            # 1. Direct geometric check against spill polygon
            if spill_poly is not None:
                pt = Point(ping_lon, ping_lat)
                if spill_poly.contains(pt) or spill_poly.touches(pt):
                    intersected = True

            # 2. Match with backtrack points and direct slick locus
            # Check distance to observed detection centroid at this ping
            dist_to_centroid = haversine_distance_km(ping_lat, ping_lon, spill_centroid["lat"], spill_centroid["lon"])
            if dist_to_centroid < min_cpa_km:
                min_cpa_km = dist_to_centroid
                best_vessel_ping = ping

            if bt_with_dt:
                # Find backtrack point with smallest absolute time difference
                closest_bt = min(bt_with_dt, key=lambda x: abs((x[0] - ping_dt).total_seconds()))
                bt_dt, bp = closest_bt
                time_diff_min = abs((bt_dt - ping_dt).total_seconds()) / 60.0

                # Compute geographic distance between vessel at ping_dt and spill at bt_dt
                dist_to_bt = haversine_distance_km(ping_lat, ping_lon, bp["lat"], bp["lon"])

                # If distance is within the dispersion uncertainty radius, flag intersection
                if dist_to_bt <= bp.get("uncertainty_radius_km", 0.5):
                    intersected = True

                if dist_to_bt < min_cpa_km:
                    min_cpa_km = dist_to_bt
                    best_vessel_ping = ping
                    best_backtrack_point = bp

        # Speed anomaly detection:
        # Check if vessel significantly slowed down near the spill area (e.g. discharging bilge water while lingering)
        speeds = [p.get("sog", 0.0) for p in track if "sog" in p]
        avg_speed = sum(speeds) / max(1, len(speeds))
        min_speed = min(speeds) if speeds else 0.0
        speed_drop = avg_speed - min_speed

        speed_anomaly = (min_speed < 4.0 and avg_speed > 8.0) or (speed_drop > 6.0)

        cpa_km_rounded = round(min_cpa_km, 2) if min_cpa_km != float("inf") else 99.9

        return {
            "mmsi": vessel.get("mmsi"),
            "vessel_name": vessel.get("vessel_name", f"MMSI-{vessel.get('mmsi')}"),
            "vessel_type": vessel.get("vessel_type", "Unknown"),
            "cpa_km": cpa_km_rounded,
            "cpa_ping": best_vessel_ping,
            "best_backtrack_point": best_backtrack_point,
            "spill_intersected": intersected,
            "speed_anomaly": speed_anomaly,
            "avg_speed_knots": round(avg_speed, 1),
            "min_speed_knots": round(min_speed, 1),
            "course_at_cpa": best_vessel_ping.get("cog", 0.0) if best_vessel_ping else 0.0,
            "time_at_cpa": best_vessel_ping.get("timestamp") if best_vessel_ping else None
        }
