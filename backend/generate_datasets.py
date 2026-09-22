"""
Dataset & SAR Imagery Generator for Oil Spill Intelligence
---------------------------------------------------------
Generates:
1. scenario_chennai.json (matching SIH diagram: 13.052° N, 80.318° E, 2.85 km², Vessel A, B, C, D)
2. scenario_mumbai_high.json (Mumbai High Arabian Sea corridor)
3. Synthetic Sentinel-1 SAR imagery raster patches
"""


import os
import json
import math
import numpy as np
import cv2
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "sample_data")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "sar_images"), exist_ok=True)


def generate_chennai_scenario():
    spill_lat = 13.052
    spill_lon = 80.318
    spill_area = 2.85
    detect_time = "2026-05-12T10:30:00Z"

    # Base time
    t_detect = datetime(2026, 5, 12, 10, 30, 0)

    # 1. Vessel A: Primary Suspect (Tanker, passes right through the origin at 10:15 - 10:28 AM)
    vessel_a_track = []
    for m in range(0, 150, 10):  # 2.5 hours
        t = t_detect - timedelta(minutes=150 - m)
        # Heading approx 210 degrees (South-South-West towards Chennai port)
        # Closer to spill at 10:20 AM (m=130)
        progress = m / 150.0
        # Starts north-east at 13.12, 80.34 and tracks south-west to 13.02, 80.30
        lat = 13.120 - progress * 0.100
        lon = 80.340 - progress * 0.045
        # Pass right at 0.45km from 13.052, 80.318 around 10:25
        speed = 12.6 if m > 90 else 13.4
        vessel_a_track.append({
            "timestamp": t.isoformat() + "Z",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": speed,
            "cog": 210.0,
            "heading": 210
        })

    # 2. Vessel B: Medium Suspect (Container Ship, curves north of spill area at ~1.8 km distance)
    vessel_b_track = []
    for m in range(0, 150, 10):
        t = t_detect - timedelta(minutes=150 - m)
        progress = m / 150.0
        # Curves from north-west (13.085, 80.295) towards south-east (13.045, 80.355)
        lat = 13.085 - progress * 0.040
        lon = 80.295 + progress * 0.060
        vessel_b_track.append({
            "timestamp": t.isoformat() + "Z",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": 15.2,
            "cog": 135.0,
            "heading": 134
        })

    # 3. Vessel C: Low Suspect (Bulk Carrier, 7.5 km East)
    vessel_c_track = []
    for m in range(0, 150, 10):
        t = t_detect - timedelta(minutes=150 - m)
        progress = m / 150.0
        lat = 13.090 - progress * 0.080
        lon = 80.390 + progress * 0.010
        vessel_c_track.append({
            "timestamp": t.isoformat() + "Z",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": 14.0,
            "cog": 165.0,
            "heading": 165
        })

    # 4. Vessel D: Low Suspect (Tug / Offshore, 8.5 km South-East moving South)
    vessel_d_track = []
    for m in range(0, 150, 10):
        t = t_detect - timedelta(minutes=150 - m)
        progress = m / 150.0
        lat = 13.020 - progress * 0.050
        lon = 80.360 + progress * 0.010
        vessel_d_track.append({
            "timestamp": t.isoformat() + "Z",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": 9.5,
            "cog": 175.0,
            "heading": 175
        })

    vessels = [
        {
            "mmsi": "123456789",
            "vessel_name": "Vessel A",
            "vessel_type": "Tanker",
            "flag": "Panama",
            "length": 240,
            "width": 42,
            "draught": 14.5,
            "destination": "Chennai Port",
            "track": vessel_a_track
        },
        {
            "mmsi": "412893210",
            "vessel_name": "Vessel B",
            "vessel_type": "Container Ship",
            "flag": "Liberia",
            "length": 294,
            "width": 32,
            "draught": 11.2,
            "destination": "Colombo",
            "track": vessel_b_track
        },
        {
            "mmsi": "636015482",
            "vessel_name": "Vessel C",
            "vessel_type": "Bulk Carrier",
            "flag": "Marshall Islands",
            "length": 190,
            "width": 30,
            "draught": 9.8,
            "destination": "Visakhapatnam",
            "track": vessel_c_track
        },
        {
            "mmsi": "538007192",
            "vessel_name": "Vessel D",
            "vessel_type": "Tug / Supply",
            "flag": "India",
            "length": 65,
            "width": 15,
            "draught": 5.2,
            "destination": "Ennore Anchorage",
            "track": vessel_d_track
        }
    ]

    # Generate 28 background vessels (fishing boats, small cargo, distant ferries) to total 32 vessels
    np.random.seed(42)
    names_pool = ["Ocean Star", "Sea Breeze", "Coral Explorer", "Pacific Trader", "Bengal Express", "Southern Pearl", "Marina King", "Blue Horizon"]
    for i in range(5, 33):
        v_mmsi = f"419{i:06d}"
        v_name = f"{names_pool[(i - 5) % len(names_pool)]} {i}"
        v_type = "Fishing" if i % 3 == 0 else ("Cargo" if i % 2 == 0 else "Offshore Tug")
        # Position dispersed 15 - 35 km away
        angle = np.random.uniform(0, 2 * math.pi)
        dist = np.random.uniform(12, 32)
        base_lat = spill_lat + (dist / 111.0) * math.sin(angle)
        base_lon = spill_lon + (dist / (111.0 * math.cos(math.radians(spill_lat)))) * math.cos(angle)
        
        bg_track = []
        heading = np.random.uniform(0, 360)
        speed = np.random.uniform(6.0, 16.0)
        for m in range(0, 150, 15):
            t = t_detect - timedelta(minutes=150 - m)
            step_h = (m / 60.0)
            cur_lat = base_lat + (speed * 1.852 * step_h * math.cos(math.radians(heading))) / 111.0
            cur_lon = base_lon + (speed * 1.852 * step_h * math.sin(math.radians(heading))) / 111.0
            bg_track.append({
                "timestamp": t.isoformat() + "Z",
                "lat": round(cur_lat, 5),
                "lon": round(cur_lon, 5),
                "sog": round(speed, 1),
                "cog": round(heading, 1)
            })

        vessels.append({
            "mmsi": v_mmsi,
            "vessel_name": v_name,
            "vessel_type": v_type,
            "flag": "India" if i % 2 == 0 else "Singapore",
            "length": 80,
            "width": 14,
            "draught": 6.0,
            "destination": "Bay of Bengal",
            "track": bg_track
        })

    # Spill polygon around 13.052, 80.318
    # Elongated organic slick polygon
    slick_poly = []
    num_pts = 16
    r_lat = 0.014  # Approx ~1.5 km across
    r_lon = 0.010
    for idx in range(num_pts):
        ang = (idx / num_pts) * 2 * math.pi
        # Modulate radius to give natural organic slick edges
        r_mod = 1.0 + 0.25 * math.sin(3 * ang) + 0.15 * math.cos(2 * ang)
        p_lat = spill_lat + r_lat * r_mod * math.sin(ang)
        p_lon = spill_lon + r_lon * r_mod * math.cos(ang)
        slick_poly.append([round(p_lon, 5), round(p_lat, 5)])
    slick_poly.append(slick_poly[0])

    scenario_chennai = {
        "id": "scenario-chennai-sih26143",
        "name": "SIH26143 - Bay of Bengal / Chennai Coast",
        "description": "Satellite SAR oil spill incident off Chennai coast with 32 correlated vessel movements.",
        "location_name": "13.052° N, 80.318° E (Bay of Bengal, Chennai Offshore)",
        "spill": {
            "detection_time": "12 May 2026, 10:30 AM",
            "detection_timestamp": detect_time,
            "sensor": "Sentinel-1 (SAR C-Band)",
            "area_km2": spill_area,
            "confidence": 0.92,
            "centroid": {"lat": spill_lat, "lon": spill_lon},
            "polygon": slick_poly,
            "expansion_history": [
                {"time": "08:00", "area_km2": 0.40},
                {"time": "08:30", "area_km2": 0.75},
                {"time": "09:00", "area_km2": 1.15},
                {"time": "09:30", "area_km2": 1.70},
                {"time": "10:00", "area_km2": 2.25},
                {"time": "10:30", "area_km2": 2.85},
                {"time": "11:00", "area_km2": 3.40}
            ]
        },
        "drift_params": {
            "current_speed_knots": 0.8,
            "current_dir_deg": 45.0,
            "wind_speed_knots": 12.0,
            "wind_dir_deg": 60.0
        },
        "vessels": vessels
    }

    with open(os.path.join(DATA_DIR, "scenario_chennai.json"), "w") as f:
        json.dump(scenario_chennai, f, indent=2)
    print("Generated scenario_chennai.json")


def generate_mumbai_scenario():
    spill_lat = 19.420
    spill_lon = 71.310
    spill_area = 4.12
    detect_time = "2026-05-14T06:45:00Z"
    t_detect = datetime(2026, 5, 14, 6, 45, 0)

    # Tanker "Arabian Voyager"
    vessel_1_track = []
    for m in range(0, 180, 15):
        t = t_detect - timedelta(minutes=180 - m)
        progress = m / 180.0
        lat = 19.480 - progress * 0.110
        lon = 71.260 + progress * 0.090
        vessel_1_track.append({
            "timestamp": t.isoformat() + "Z",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": 11.8 if m > 90 else 14.2,
            "cog": 145.0
        })

    # Cargo "Indus Star"
    vessel_2_track = []
    for m in range(0, 180, 15):
        t = t_detect - timedelta(minutes=180 - m)
        progress = m / 180.0
        lat = 19.450 - progress * 0.050
        lon = 71.390 - progress * 0.040
        vessel_2_track.append({
            "timestamp": t.isoformat() + "Z",
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "sog": 16.5,
            "cog": 220.0
        })

    vessels = [
        {
            "mmsi": "355912401",
            "vessel_name": "Arabian Voyager",
            "vessel_type": "Crude Oil Tanker",
            "flag": "Panama",
            "length": 310,
            "width": 58,
            "draught": 18.2,
            "destination": "Mumbai JNPT",
            "track": vessel_1_track
        },
        {
            "mmsi": "419001844",
            "vessel_name": "Indus Star",
            "vessel_type": "Container Ship",
            "flag": "India",
            "length": 260,
            "width": 38,
            "draught": 12.5,
            "destination": "Kandla Port",
            "track": vessel_2_track
        }
    ]

    # Generate 16 background corridor vessels (offshore supply, tugs, fishing, tankers) to total 18 vessels
    np.random.seed(84)
    mumbai_names_pool = ["Sindhu Sagar", "Arabian Pearl", "Western Crest", "Konkan Pride", "Albatross", "Sagar Ratna", "Trident Voyager", "Gulf Trader"]
    for i in range(3, 19):
        v_mmsi = f"419100{i:03d}"
        v_name = f"{mumbai_names_pool[(i - 3) % len(mumbai_names_pool)]} {i}"
        v_type = "Offshore Supply" if i % 3 == 0 else ("Fishing" if i % 2 == 0 else "Oil Tanker")
        angle = np.random.uniform(0, 2 * math.pi)
        dist = np.random.uniform(10, 30)
        base_lat = spill_lat + (dist / 111.0) * math.sin(angle)
        base_lon = spill_lon + (dist / (111.0 * math.cos(math.radians(spill_lat)))) * math.cos(angle)
        
        bg_track = []
        heading = np.random.uniform(0, 360)
        speed = np.random.uniform(8.0, 15.0)
        for m in range(0, 180, 15):
            t = t_detect - timedelta(minutes=180 - m)
            step_h = (m / 60.0)
            cur_lat = base_lat + (speed * 1.852 * step_h * math.cos(math.radians(heading))) / 111.0
            cur_lon = base_lon + (speed * 1.852 * step_h * math.sin(math.radians(heading))) / 111.0
            bg_track.append({
                "timestamp": t.isoformat() + "Z",
                "lat": round(cur_lat, 5),
                "lon": round(cur_lon, 5),
                "sog": round(speed, 1),
                "cog": round(heading, 1)
            })

        vessels.append({
            "mmsi": v_mmsi,
            "vessel_name": v_name,
            "vessel_type": v_type,
            "flag": "India" if i % 2 == 0 else "Liberia",
            "length": 95,
            "width": 18,
            "draught": 7.5,
            "destination": "Mumbai Port",
            "track": bg_track
        })

    slick_poly = []
    for idx in range(16):
        ang = (idx / 16) * 2 * math.pi
        r_mod = 1.0 + 0.3 * math.sin(2 * ang)
        p_lat = spill_lat + 0.018 * r_mod * math.sin(ang)
        p_lon = spill_lon + 0.015 * r_mod * math.cos(ang)
        slick_poly.append([round(p_lon, 5), round(p_lat, 5)])
    slick_poly.append(slick_poly[0])

    scenario_mumbai = {
        "id": "scenario-mumbai-high",
        "name": "Mumbai High Offshore Corridors (Arabian Sea)",
        "description": "Oil discharge detection near offshore extraction zones and major tanker shipping lanes.",
        "location_name": "19.420° N, 71.310° E (Mumbai High Corridor)",
        "spill": {
            "detection_time": "14 May 2026, 06:45 AM",
            "detection_timestamp": detect_time,
            "sensor": "Sentinel-1 (SAR C-Band)",
            "area_km2": spill_area,
            "confidence": 0.94,
            "centroid": {"lat": spill_lat, "lon": spill_lon},
            "polygon": slick_poly,
            "expansion_history": [
                {"time": "04:00", "area_km2": 0.80},
                {"time": "05:00", "area_km2": 1.90},
                {"time": "06:00", "area_km2": 3.30},
                {"time": "06:45", "area_km2": 4.12}
            ]
        },
        "drift_params": {
            "current_speed_knots": 1.1,
            "current_dir_dir": 110.0,
            "wind_speed_knots": 15.0,
            "wind_dir_deg": 135.0
        },
        "vessels": vessels
    }

    with open(os.path.join(DATA_DIR, "scenario_mumbai_high.json"), "w") as f:
        json.dump(scenario_mumbai, f, indent=2)
    print("Generated scenario_mumbai_high.json")


def generate_sar_image_patch():
    """
    Creates an authentic synthetic Sentinel-1 SAR imagery patch saved as PNG
    to display in the dashboard overview and use for live detection testing.
    """
    from backend.modules.sar_detector import SARSpillDetector
    detector = SARSpillDetector()
    patch = detector.generate_synthetic_sar_patch(width=512, height=512, spill_center_ratio=(0.52, 0.49), spill_radius=75)
    
    # Save grayscale SAR
    out_path = os.path.join(DATA_DIR, "sar_images", "sentinel1_sar_chennai.png")
    cv2.imwrite(out_path, patch)
    print(f"Generated SAR patch image at {out_path}")


if __name__ == "__main__":
    generate_chennai_scenario()
    generate_mumbai_scenario()
    generate_sar_image_patch()
