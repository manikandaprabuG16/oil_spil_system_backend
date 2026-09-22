"""
AIS Data Processing & Spatio-Temporal Filtering Engine
------------------------------------------------------
Parses, cleans, interpolates, and filters maritime AIS feeds.
Extracts candidate vessels within spatial radius R and temporal window delta_T of an incident.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import math


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two points on the Earth (in km).
    """
    R = 6371.0088  # Earth radius in kilometers
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_timestamp(ts: Any) -> datetime:
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, (int, float)):
        return datetime.utcfromtimestamp(ts)
    ts_str = str(ts).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(ts_str)
    except Exception:
        # Fallback common formats
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d %b %Y, %I:%M %p"):
            try:
                return datetime.strptime(str(ts), fmt)
            except ValueError:
                pass
        raise ValueError(f"Unable to parse timestamp: {ts}")


class AISEngine:
    def __init__(self):
        pass

    def filter_spatio_temporal(
        self,
        vessels: List[Dict[str, Any]],
        spill_lat: float,
        spill_lon: float,
        spill_time: Any,
        radius_km: float = 25.0,
        time_window_hours_before: float = 6.0,
        time_window_hours_after: float = 1.0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filters vessel tracks that were within radius_km during the critical time window.
        Returns: (candidate_vessels, total_vessels_evaluated)
        """
        spill_dt = parse_timestamp(spill_time)
        start_dt = spill_dt - timedelta(hours=time_window_hours_before)
        end_dt = spill_dt + timedelta(hours=time_window_hours_after)

        total_vessels = len(vessels)
        candidates = []

        for vessel in vessels:
            track = vessel.get("track", [])
            in_window_track = []
            min_dist = float("inf")
            min_dist_ping = None

            for ping in track:
                try:
                    p_time = parse_timestamp(ping["timestamp"])
                except Exception:
                    continue

                if start_dt <= p_time <= end_dt:
                    in_window_track.append(ping)
                    d = haversine_distance_km(spill_lat, spill_lon, ping["lat"], ping["lon"])
                    if d < min_dist:
                        min_dist = d
                        min_dist_ping = ping

            # If vessel entered within the spatial search boundary during the temporal window
            if min_dist <= radius_km and in_window_track:
                vessel_copy = dict(vessel)
                vessel_copy["min_observed_distance_km"] = round(min_dist, 2)
                vessel_copy["closest_ping"] = min_dist_ping
                vessel_copy["filtered_track"] = in_window_track
                
                # Compute telemetry stats
                speeds = [p.get("sog", 0.0) for p in in_window_track if "sog" in p]
                if speeds:
                    vessel_copy["avg_speed_knots"] = round(sum(speeds) / len(speeds), 1)
                    vessel_copy["max_speed_knots"] = round(max(speeds), 1)
                    vessel_copy["min_speed_knots"] = round(min(speeds), 1)
                    # Check for sudden speed deceleration
                    speed_variance = np_var = sum((s - vessel_copy["avg_speed_knots"])**2 for s in speeds) / len(speeds)
                    vessel_copy["speed_variance"] = round(speed_variance, 2)
                else:
                    vessel_copy["avg_speed_knots"] = 0.0
                    vessel_copy["max_speed_knots"] = 0.0
                    vessel_copy["min_speed_knots"] = 0.0
                    vessel_copy["speed_variance"] = 0.0

                candidates.append(vessel_copy)

        return candidates, total_vessels

    def interpolate_trajectory(
        self, track: List[Dict[str, Any]], interval_minutes: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Interpolates track positions to create smooth, synchronized time steps for simulation playback.
        """
        if len(track) < 2:
            return track

        interpolated = []
        for i in range(len(track) - 1):
            p1 = track[i]
            p2 = track[i + 1]
            t1 = parse_timestamp(p1["timestamp"])
            t2 = parse_timestamp(p2["timestamp"])
            duration_sec = (t2 - t1).total_seconds()

            interpolated.append(p1)
            if duration_sec <= interval_minutes * 60:
                continue

            steps = int(duration_sec // (interval_minutes * 60))
            for s in range(1, steps):
                frac = s / (steps + 1)
                t_interp = t1 + timedelta(seconds=duration_sec * frac)
                lat_interp = p1["lat"] + frac * (p2["lat"] - p1["lat"])
                lon_interp = p1["lon"] + frac * (p2["lon"] - p1["lon"])
                sog_interp = p1.get("sog", 0) + frac * (p2.get("sog", 0) - p1.get("sog", 0))
                cog_interp = p1.get("cog", 0) + frac * (p2.get("cog", 0) - p1.get("cog", 0))

                interpolated.append({
                    "timestamp": t_interp.isoformat(),
                    "lat": round(lat_interp, 6),
                    "lon": round(lon_interp, 6),
                    "sog": round(sog_interp, 1),
                    "cog": round(cog_interp, 1),
                    "interpolated": True
                })

        interpolated.append(track[-1])
        return interpolated

    def parse_ais_csv(self, csv_text: str) -> List[Dict[str, Any]]:
        """
        Parses standard maritime AIS CSV format (MarineCadastre / AISHub / Port Authority).
        Handles column variations:
        - MMSI / mmsi
        - BaseDateTime / timestamp / time / date_time_utc
        - LAT / Latitude / lat
        - LON / Longitude / lon
        - SOG / Speed / speed
        - COG / Course / course
        - Heading / heading
        - VesselName / vessel_name / name
        - VesselType / vessel_type / type
        - Draft / Draught / draft
        """
        import csv
        import io

        f = io.StringIO(csv_text)
        reader = csv.DictReader(f)
        
        # Group rows by MMSI
        vessels_by_mmsi = {}

        for row in reader:
            # Normalize keys to lowercase stripped
            norm_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}

            mmsi = norm_row.get("mmsi")
            if not mmsi:
                continue

            # Extract lat / lon
            lat_str = norm_row.get("lat") or norm_row.get("latitude")
            lon_str = norm_row.get("lon") or norm_row.get("longitude")
            if not lat_str or not lon_str:
                continue

            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except ValueError:
                continue

            # Extract timestamp
            ts_str = norm_row.get("basedatetime") or norm_row.get("timestamp") or norm_row.get("time") or norm_row.get("date_time_utc")
            if not ts_str:
                continue

            # Telemetry fields
            try:
                sog = float(norm_row.get("sog") or norm_row.get("speed") or 0.0)
            except ValueError:
                sog = 0.0

            try:
                cog = float(norm_row.get("cog") or norm_row.get("course") or 0.0)
            except ValueError:
                cog = 0.0

            try:
                heading = float(norm_row.get("heading") or cog)
            except ValueError:
                heading = cog

            vessel_name = norm_row.get("vesselname") or norm_row.get("vessel_name") or norm_row.get("name") or f"MMSI-{mmsi}"
            vessel_type = norm_row.get("vesseltype") or norm_row.get("vessel_type") or norm_row.get("type") or "Cargo"
            flag = norm_row.get("flag") or "International"
            destination = norm_row.get("destination") or "Open Sea"

            ping = {
                "timestamp": ts_str,
                "lat": round(lat, 5),
                "lon": round(lon, 5),
                "sog": round(sog, 1),
                "cog": round(cog, 1),
                "heading": round(heading, 1)
            }

            if mmsi not in vessels_by_mmsi:
                vessels_by_mmsi[mmsi] = {
                    "mmsi": str(mmsi),
                    "vessel_name": vessel_name,
                    "vessel_type": vessel_type,
                    "flag": flag,
                    "destination": destination,
                    "track": []
                }

            vessels_by_mmsi[mmsi]["track"].append(ping)

        # Sort each vessel's track chronologically
        vessel_list = []
        for mmsi, v_data in vessels_by_mmsi.items():
            try:
                v_data["track"].sort(key=lambda p: parse_timestamp(p["timestamp"]))
            except Exception:
                pass
            vessel_list.append(v_data)

        return vessel_list
