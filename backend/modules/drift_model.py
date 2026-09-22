"""
Hydrodynamic & Marine Drift Backtracking Engine
------------------------------------------------
Calculates oil slick advection (drift) and weathering:
1. Windage factor (3.0% - 3.5% of wind speed) + 100% surface current vector
2. Temporal backtracking to determine likely discharge origin location and time window
3. Fay's spreading model simulation for spill expansion over time
"""

import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from .ais_engine import parse_timestamp, haversine_distance_km


class DriftModel:
    def __init__(self, wind_factor: float = 0.033, coriolis_deflection_deg: float = 5.0):
        """
        :param wind_factor: Ratio of wind speed transferred to surface slick (standard NOAA GNOME rule: 3% - 3.5%).
        :param coriolis_deflection_deg: Slight deflection to right in Northern Hemisphere.
        """
        self.wind_factor = wind_factor
        self.coriolis_deflection = coriolis_deflection_deg

    def compute_drift_velocity(
        self,
        current_speed_knots: float,
        current_direction_deg: float,
        wind_speed_knots: float,
        wind_direction_deg: float
    ) -> Tuple[float, float]:
        """
        Computes the resultant slick drift vector: (speed in knots, heading in degrees).
        Note: Oceanographic direction convention is 'towards which flow moves'.
        """
        # Current vector components (knots)
        cur_rad = math.radians(current_direction_deg)
        u_cur = current_speed_knots * math.sin(cur_rad)
        v_cur = current_speed_knots * math.cos(cur_rad)

        # Wind drift vector components (knots, with windage factor)
        # Wind blowing TOWARDS direction = (wind_direction + 180) % 360 or standard meteorological.
        # Here we assume wind_direction is direction wind is BLOWING TOWARDS, deflected slightly.
        deflected_wind_dir = wind_direction_deg + self.coriolis_deflection
        wind_rad = math.radians(deflected_wind_dir)
        u_wind = (wind_speed_knots * self.wind_factor) * math.sin(wind_rad)
        v_wind = (wind_speed_knots * self.wind_factor) * math.cos(wind_rad)

        # Net drift vector
        u_net = u_cur + u_wind
        v_net = v_cur + v_wind

        net_speed = math.sqrt(u_net**2 + v_net**2)
        net_heading = (math.degrees(math.atan2(u_net, v_net)) + 360) % 360
        return net_speed, net_heading

    def backtrack_spill_origin(
        self,
        spill_lat: float,
        spill_lon: float,
        detect_time: Any,
        hours_back: float = 4.0,
        current_speed_knots: float = 0.8,
        current_direction_deg: float = 45.0,
        wind_speed_knots: float = 12.0,
        wind_direction_deg: float = 60.0,
        step_minutes: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Backtracks the spill position backwards in time from detection time.
        Generates origin trajectory and uncertainty dispersion radius.
        """
        detect_dt = parse_timestamp(detect_time)
        drift_speed_knots, drift_heading_deg = self.compute_drift_velocity(
            current_speed_knots, current_direction_deg, wind_speed_knots, wind_direction_deg
        )

        # 1 knot = 1.852 km/h
        drift_speed_kmh = drift_speed_knots * 1.852
        
        # Reverse heading for backtracking (180 degrees opposite)
        backtrack_heading_rad = math.radians((drift_heading_deg + 180) % 360)

        history = []
        total_steps = int((hours_back * 60) // step_minutes)

        curr_lat = spill_lat
        curr_lon = spill_lon

        # Initial point at detection time
        history.append({
            "timestamp": detect_dt.isoformat(),
            "hours_before_detect": 0.0,
            "lat": round(curr_lat, 5),
            "lon": round(curr_lon, 5),
            "uncertainty_radius_km": 0.3,  # Initial detection boundary uncertainty
            "drift_speed_knots": round(drift_speed_knots, 2),
            "drift_heading_deg": round(drift_heading_deg, 1)
        })

        # Earth degree conversion approximation near latitude
        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * math.cos(math.radians(spill_lat))

        for step in range(1, total_steps + 1):
            elapsed_hours = (step * step_minutes) / 60.0
            step_dt = detect_dt - timedelta(minutes=step * step_minutes)

            # Distance stepped in this interval (km)
            dist_step_km = drift_speed_kmh * (step_minutes / 60.0)

            # Move backwards along backtrack heading
            dlat = (dist_step_km * math.cos(backtrack_heading_rad)) / km_per_deg_lat
            dlon = (dist_step_km * math.sin(backtrack_heading_rad)) / km_per_deg_lon

            curr_lat += dlat
            curr_lon += dlon

            # Spreading / diffusion uncertainty increases as we go back in time
            dispersion_radius_km = 0.3 + 0.25 * math.sqrt(elapsed_hours)

            history.append({
                "timestamp": step_dt.isoformat(),
                "hours_before_detect": round(elapsed_hours, 2),
                "lat": round(curr_lat, 5),
                "lon": round(curr_lon, 5),
                "uncertainty_radius_km": round(dispersion_radius_km, 2),
                "drift_speed_knots": round(drift_speed_knots, 2),
                "drift_heading_deg": round(drift_heading_deg, 1)
            })

        return history

    def simulate_area_expansion(
        self, initial_area_km2: float, hours: int = 6, base_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Simulates the growth of slick area over time matching Fay's empirical spreading curves.
        """
        if base_time is None:
            base_time = datetime.now() - timedelta(hours=hours)

        expansion_curve = []
        # Area increases rapidly at first then plateaus as lighter fractions evaporate
        for h in range(hours + 1):
            t_point = base_time + timedelta(hours=h)
            # Growth multiplier formula
            mult = 0.25 + 0.75 * math.pow(h / max(1, hours), 0.85)
            area = initial_area_km2 * mult
            expansion_curve.append({
                "time": t_point.strftime("%H:%M"),
                "timestamp": t_point.isoformat(),
                "hour_offset": h,
                "area_km2": round(area, 2)
            })
        return expansion_curve

    def calculate_polygon_perimeter_km(
        self, polygon: List[List[float]], fallback_area_km2: Optional[float] = None
    ) -> float:
        """
        Computes accurate perimeter of a GeoJSON polygon in kilometers using Haversine distance.
        Polygon format: [[lon, lat], [lon, lat], ...]
        """
        if not polygon or len(polygon) < 3:
            if fallback_area_km2 and fallback_area_km2 > 0:
                # Shape factor approximation for irregular maritime oil slicks (elongated plume)
                return round(2.3 * 2 * math.sqrt(math.pi * fallback_area_km2), 2)
            return 0.0

        total_perimeter = 0.0
        n = len(polygon)
        for i in range(n - 1):
            p1 = polygon[i]
            p2 = polygon[i + 1]
            # p is [lon, lat]
            total_perimeter += haversine_distance_km(p1[1], p1[0], p2[1], p2[0])

        # Ensure loop is closed if first and last point are different
        p_first = polygon[0]
        p_last = polygon[-1]
        if (p_first[0] != p_last[0] or p_first[1] != p_last[1]):
            total_perimeter += haversine_distance_km(p_last[1], p_last[0], p_first[1], p_first[0])

        return round(total_perimeter, 2)

    def calculate_oil_spill_volume_and_resources(
        self,
        area_km2: float,
        perimeter_km: float,
        thickness_mm: float = 0.25,
        recovery_window_hours: float = 48.0,
        skimmer_capacity_m3h: float = 40.0,
        tanker_capacity_m3: float = 1500.0,
        water_cut_pct: float = 35.0
    ) -> Dict[str, Any]:
        """
        Calculates total spill volume, mass, and required clean-up equipment:
        - Oil volume (m³, barrels, metric tons)
        - Skimmers needed (based on ASTM / USCG Effective Daily Recovery Capacity)
        - Oil storage tankers needed (accounting for emulsified water cut)
        - Containment boom meters needed (based on perimeter & encirclement factor)
        - Observation & surveillance assets (patrol boats, drones)
        """
        # Volume (m³) = Area (m²) * Thickness (m)
        # Area in km² = Area * 1,000,000 m²
        # Thickness in mm = Thickness / 1,000 m
        # Volume (m³) = Area (km²) * Thickness (mm) * 1,000
        volume_m3 = round(area_km2 * thickness_mm * 1000.0, 2)
        volume_bbl = round(volume_m3 * 6.28981, 1)
        crude_density = 0.88  # Average metric tons per m³ for medium-heavy crude
        volume_tons = round(volume_m3 * crude_density, 2)
        volume_gallons = round(volume_m3 * 264.172, 0)

        # Bonn Agreement classification
        if thickness_mm < 0.0003:
            bonn_code = 1
            bonn_label = "Code 1: Sheen (<0.0003 mm)"
        elif thickness_mm < 0.005:
            bonn_code = 2
            bonn_label = "Code 2: Rainbow (0.0003–0.005 mm)"
        elif thickness_mm < 0.05:
            bonn_code = 3
            bonn_label = "Code 3: Metallic (0.005–0.05 mm)"
        elif thickness_mm < 0.20:
            bonn_code = 4
            bonn_label = "Code 4: Discontinuous True Oil (0.05–0.20 mm)"
        else:
            bonn_code = 5
            bonn_label = "Code 5: Continuous Heavy Crude (>0.20 mm)"

        # Skimmer capacity calculation
        # USCG / IMO EDRC standard rule: Derate skimmer nameplate capacity by 20%-25% for real sea state
        edrc_derate = 0.25
        effective_hourly_m3 = skimmer_capacity_m3h * edrc_derate
        total_skimmer_recovery_window_m3 = effective_hourly_m3 * max(12.0, recovery_window_hours)

        skimmers_needed = max(1, math.ceil(volume_m3 / max(1.0, total_skimmer_recovery_window_m3)))

        # Oil Tanker / Storage Vessel calculation
        # Skimmed fluid includes emulsion water cut (typically 25%-40% water)
        total_fluid_emulsion_m3 = round(volume_m3 * (1.0 + (water_cut_pct / 100.0)), 2)
        total_fluid_bbl = round(total_fluid_emulsion_m3 * 6.28981, 1)
        tankers_needed = max(1, math.ceil(total_fluid_emulsion_m3 / max(100.0, tanker_capacity_m3)))

        # Containment Booms: 1.25x perimeter to allow catenary curve and sweep angles
        boom_length_km = round(perimeter_km * 1.25, 2)
        boom_length_meters = round(boom_length_km * 1000.0, 0)

        # Observation & Surveillance Patrol assets: 1 vessel per 8 km perimeter
        observation_vessels = max(1, math.ceil(perimeter_km / 8.0))
        surveillance_drones = max(1, math.ceil(perimeter_km / 12.0))

        return {
            "thickness_mm": thickness_mm,
            "thickness_microns": round(thickness_mm * 1000.0, 1),
            "bonn_code": bonn_code,
            "bonn_label": bonn_label,
            "area_km2": area_km2,
            "perimeter_km": perimeter_km,
            "volume_m3": volume_m3,
            "volume_bbl": volume_bbl,
            "volume_tons": volume_tons,
            "volume_gallons": volume_gallons,
            "total_fluid_emulsion_m3": total_fluid_emulsion_m3,
            "total_fluid_bbl": total_fluid_bbl,
            "water_cut_pct": water_cut_pct,
            "skimmers_needed": skimmers_needed,
            "tankers_needed": tankers_needed,
            "boom_length_km": boom_length_km,
            "boom_length_meters": boom_length_meters,
            "observation_vessels_needed": observation_vessels,
            "surveillance_drones_needed": surveillance_drones,
            "recovery_window_hours": recovery_window_hours,
            "skimmer_capacity_m3h": skimmer_capacity_m3h,
            "tanker_capacity_m3": tanker_capacity_m3
        }

    def forecast_spill_forward(
        self,
        spill_lat: float,
        spill_lon: float,
        polygon: List[List[float]],
        initial_area_km2: float,
        detect_time: Any,
        current_speed_knots: float = 0.8,
        current_direction_deg: float = 45.0,
        wind_speed_knots: float = 12.0,
        wind_direction_deg: float = 60.0,
        forecast_hours: List[int] = [0, 6, 12, 24, 48, 72],
        thickness_mm: float = 0.25
    ) -> List[Dict[str, Any]]:
        """
        Forecasts forward oil slick advection (drift) and spatial area expansion
        for specified timeline horizons (NOW, +6h, +12h, +24h, +48h, +72h).
        Includes dynamic perimeter, volume, skimmers, and tankers calculations.
        """
        detect_dt = parse_timestamp(detect_time)
        drift_speed_knots, drift_heading_deg = self.compute_drift_velocity(
            current_speed_knots, current_direction_deg, wind_speed_knots, wind_direction_deg
        )
        drift_speed_kmh = drift_speed_knots * 1.852
        heading_rad = math.radians(drift_heading_deg)

        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * math.cos(math.radians(spill_lat))

        forecasts = []

        for h in forecast_hours:
            target_dt = detect_dt + timedelta(hours=h)
            dist_km = drift_speed_kmh * h

            dlat = (dist_km * math.cos(heading_rad)) / km_per_deg_lat
            dlon = (dist_km * math.sin(heading_rad)) / km_per_deg_lon

            new_lat = spill_lat + dlat
            new_lon = spill_lon + dlon

            # Spreading expansion multiplier over time
            area_multiplier = 1.0 + 0.08 * math.pow(h, 0.75) if h > 0 else 1.0
            forecast_area = round(initial_area_km2 * area_multiplier, 2)
            scale_factor = math.sqrt(area_multiplier)

            # As slick spreads over time, thickness gradually decreases slightly due to spreading/weathering
            forecast_thickness = round(max(0.05, thickness_mm * (1.0 / (1.0 + 0.04 * math.pow(h, 0.7)))), 3)

            # Scale and translate polygon vertices relative to new centroid
            forecast_polygon = []
            if polygon:
                for pt in polygon:
                    # pt is [lon, lat]
                    lon_offset = (pt[0] - spill_lon) * scale_factor
                    lat_offset = (pt[1] - spill_lat) * scale_factor
                    forecast_polygon.append([
                        round(new_lon + lon_offset, 5),
                        round(new_lat + lat_offset, 5)
                    ])

            forecast_perimeter = self.calculate_polygon_perimeter_km(forecast_polygon, forecast_area)
            equipment = self.calculate_oil_spill_volume_and_resources(
                area_km2=forecast_area,
                perimeter_km=forecast_perimeter,
                thickness_mm=forecast_thickness
            )

            label = "NOW" if h == 0 else f"+{h}H"

            forecasts.append({
                "hours": h,
                "label": label,
                "status_display": "CURRENT DETECTION" if h == 0 else f"FORECAST (+{h}H)",
                "timestamp": target_dt.isoformat(),
                "time_display": target_dt.strftime("%d %b %Y, %I:%M %p"),
                "centroid": {
                    "lat": round(new_lat, 5),
                    "lon": round(new_lon, 5)
                },
                "area_km2": forecast_area,
                "perimeter_km": forecast_perimeter,
                "thickness_mm": forecast_thickness,
                "volume_m3": equipment["volume_m3"],
                "volume_bbl": equipment["volume_bbl"],
                "skimmers_needed": equipment["skimmers_needed"],
                "tankers_needed": equipment["tankers_needed"],
                "boom_length_km": equipment["boom_length_km"],
                "polygon": forecast_polygon,
                "drift_dist_km": round(dist_km, 2),
                "drift_speed_knots": round(drift_speed_knots, 2),
                "drift_heading_deg": round(drift_heading_deg, 1),
                "equipment": equipment
            })

        return forecasts

