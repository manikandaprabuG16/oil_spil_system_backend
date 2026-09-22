"""
AI Swarm Fleet & Autonomous Inter-Boat Communication Engine
SIH26143: Maritime Swarm Robotics for Oil Spill Containment & Recovery

Coordinates multiple Unmanned Surface Vessels (USVs) and an aerial drone (UAV)
carrying containment booms and dynamic skimmers. Simulates inter-boat M2M mesh
communication protocols, catenary boom physics, and skimmer recovery.
"""

import math
import time
import random
from typing import Dict, List, Any, Optional

class AISwarmFleetEngine:
    def __init__(self):
        self.message_history: List[Dict[str, Any]] = []

    def initialize_swarm_for_spill(
        self,
        centroid_lat: float,
        centroid_lon: float,
        spill_area_km2: float = 4.25,
        perimeter_km: float = 9.21,
        thickness_mm: float = 0.25,
        wind_dir_deg: float = 60.0,
        current_dir_deg: float = 45.0
    ) -> Dict[str, Any]:
        """
        Initializes an autonomous AI response swarm positioned downwind/downcurrent
        relative to the spill centroid to intercept and contain the drifting slick.
        """
        # Sweep angle opposes or aligns with slick drift direction
        sweep_heading = (current_dir_deg + 180.0) % 360.0
        rad_heading = math.radians(sweep_heading)
        
        # Base offset distance from centroid (~0.008 deg is ~900 meters)
        offset_dist = 0.007
        base_lat = centroid_lat + offset_dist * math.cos(rad_heading)
        base_lon = centroid_lon + offset_dist * math.sin(rad_heading)

        # Perpendicular angle for boat formation spacing
        perp_rad = rad_heading + math.pi / 2.0
        # Spacing between Alpha and Bravo (boom towing pair) ~180-220 meters (~0.0018 deg)
        aperture_deg = 0.0016

        alpha_lat = round(base_lat + (aperture_deg / 2.0) * math.cos(perp_rad), 6)
        alpha_lon = round(base_lon + (aperture_deg / 2.0) * math.sin(perp_rad), 6)

        bravo_lat = round(base_lat - (aperture_deg / 2.0) * math.cos(perp_rad), 6)
        bravo_lon = round(base_lon - (aperture_deg / 2.0) * math.sin(perp_rad), 6)

        # Charlie (Skimmer Boat) is positioned right at the apex of the U-boom pocket
        # slightly behind the midpoint of Alpha and Bravo
        pocket_lag = 0.0008
        charlie_lat = round(base_lat - pocket_lag * math.cos(rad_heading), 6)
        charlie_lon = round(base_lon - pocket_lag * math.sin(rad_heading), 6)

        # UAV Sentry hovers 120m overhead scouting the slick boundary
        uav_lat = round(centroid_lat + 0.002 * math.cos(rad_heading), 6)
        uav_lon = round(centroid_lon + 0.002 * math.sin(rad_heading), 6)

        # AI Boats fleet definitions
        boats = [
            {
                "id": "ai-usv-01",
                "callsign": "AI-USV ALPHA",
                "role": "Boom Tow Lead",
                "role_badge": "Lead Boom Tow",
                "status": "OPERATIONAL",
                "lat": alpha_lat,
                "lon": alpha_lon,
                "heading": round(current_dir_deg, 1),
                "speed_knots": 1.8,
                "battery_pct": 94,
                "fuel_pct": 89,
                "payload": {
                    "type": "Containment Boom Reel",
                    "model": "OceanFence Rapid 600m Curtain",
                    "boom_deployed_m": 250,
                    "boom_tension_kn": 38.4,
                    "max_tension_kn": 75.0,
                    "draft_submersion_cm": 45
                },
                "comms": {
                    "mesh_ip": "10.42.0.1",
                    "signal_dbm": -58,
                    "packet_loss_pct": 0.1,
                    "peer_nodes": ["ai-usv-02", "ai-usv-03", "ai-uav-01"]
                }
            },
            {
                "id": "ai-usv-02",
                "callsign": "AI-USV BRAVO",
                "role": "Boom Tow Wing",
                "role_badge": "Wing Boom Tow",
                "status": "OPERATIONAL",
                "lat": bravo_lat,
                "lon": bravo_lon,
                "heading": round(current_dir_deg, 1),
                "speed_knots": 1.8,
                "battery_pct": 92,
                "fuel_pct": 87,
                "payload": {
                    "type": "Synchronized Catenary Tow",
                    "model": "Auto-Tension Hydro-Winch 50kN",
                    "boom_deployed_m": 250,
                    "boom_tension_kn": 39.1,
                    "max_tension_kn": 75.0,
                    "aperture_spread_m": 195
                },
                "comms": {
                    "mesh_ip": "10.42.0.2",
                    "signal_dbm": -61,
                    "packet_loss_pct": 0.2,
                    "peer_nodes": ["ai-usv-01", "ai-usv-03", "ai-uav-01"]
                }
            },
            {
                "id": "ai-usv-03",
                "callsign": "AI-USV CHARLIE",
                "role": "Heavy Skimmer Recovery",
                "role_badge": "Skimmer Active",
                "status": "SKIMMING_ACTIVE",
                "lat": charlie_lat,
                "lon": charlie_lon,
                "heading": round(current_dir_deg, 1),
                "speed_knots": 1.6,
                "battery_pct": 88,
                "fuel_pct": 82,
                "payload": {
                    "type": "Dynamic Oleophilic Brush & Weir Skimmer",
                    "model": "AquaSkim Apex-60 Autonomous",
                    "pump_rate_m3h": 58.5,
                    "efficiency_pct": 84,
                    "emulsion_recovered_m3": 48.2,
                    "tank_capacity_m3": 120.0,
                    "tank_fill_pct": 40.2
                },
                "comms": {
                    "mesh_ip": "10.42.0.3",
                    "signal_dbm": -55,
                    "packet_loss_pct": 0.0,
                    "peer_nodes": ["ai-usv-01", "ai-usv-02", "ai-uav-01"]
                }
            },
            {
                "id": "ai-uav-01",
                "callsign": "AI-UAV SENTRY",
                "role": "Aerial Recon & Swarm Vectoring",
                "role_badge": "Slick Vectoring",
                "status": "PATROL_ACTIVE",
                "lat": uav_lat,
                "lon": uav_lon,
                "altitude_m": 125,
                "heading": round(wind_dir_deg, 1),
                "speed_knots": 14.5,
                "battery_pct": 78,
                "payload": {
                    "type": "Multispectral FLIR & SAR Optical Sensor",
                    "sensor_fov_m": 450,
                    "slick_front_detected": True,
                    "peak_thickness_loc": {"lat": round(centroid_lat, 5), "lon": round(centroid_lon, 5)}
                },
                "comms": {
                    "mesh_ip": "10.42.0.10",
                    "signal_dbm": -52,
                    "packet_loss_pct": 0.0,
                    "peer_nodes": ["ai-usv-01", "ai-usv-02", "ai-usv-03"]
                }
            }
        ]

        # Boom Catenary Curve points connecting Alpha -> Charlie -> Bravo
        boom_catenary = self._generate_boom_catenary(
            (alpha_lat, alpha_lon),
            (bravo_lat, bravo_lon),
            (charlie_lat, charlie_lon),
            num_segments=16
        )

        # Initial M2M Inter-Boat Communications
        initial_messages = self.generate_m2m_transmissions(boats)

        return {
            "swarm_id": "swarm-alpha-marine",
            "state": "ACTIVE_RECOVERY",
            "mode": "COORDINATED_U_SWEEP",
            "centroid": {"lat": centroid_lat, "lon": centroid_lon},
            "boats": boats,
            "containment_boom": {
                "length_m": 500,
                "catenary_points": boom_catenary,
                "tow_leaders": ["ai-usv-01", "ai-usv-02"],
                "pocket_skimmer": "ai-usv-03",
                "tension_kn": 38.8,
                "safety_margin_pct": 48
            },
            "skimmer_operations": {
                "active_units": 1,
                "nominal_recovery_rate_m3h": 58.5,
                "current_recovery_m3": 48.2,
                "target_volume_m3": round(spill_area_km2 * thickness_mm * 1000.0, 1),
                "emulsion_ratio": "35% water cut"
            },
            "comms_mesh": {
                "network_ssid": "MARITIME-AI-SWARM-5G",
                "frequency": "5.8 GHz COFDM P2P",
                "active_nodes": 4,
                "topology": "Fully Meshed Decentralized",
                "average_latency_ms": 14.2,
                "packet_delivery_rate_pct": 99.8,
                "encryption": "AES-256 Marine Cryptographic Token"
            },
            "recent_transmissions": initial_messages
        }

    def _generate_boom_catenary(
        self,
        p1: tuple,
        p2: tuple,
        apex: tuple,
        num_segments: int = 16
    ) -> List[List[float]]:
        """
        Generates realistic catenary / parabolic curvature for oil containment boom
        strung between Boat 1 (Alpha), passing through the pocket skimmer (Charlie), to Boat 2 (Bravo).
        """
        curve_points = []
        for i in range(num_segments + 1):
            t = i / float(num_segments)
            # Quadratic Bezier curve between p1, apex, p2
            # B(t) = (1-t)^2 * p1 + 2(1-t)t * apex + t^2 * p2
            lat = ((1 - t) ** 2) * p1[0] + 2 * (1 - t) * t * apex[0] + (t ** 2) * p2[0]
            lon = ((1 - t) ** 2) * p1[1] + 2 * (1 - t) * t * apex[1] + (t ** 2) * p2[1]
            curve_points.append([round(lat, 6), round(lon, 6)])
        return curve_points

    def generate_m2m_transmissions(self, boats: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generates rich, authentic autonomous M2M (Machine-to-Machine) telemetry
        messages exchanged between the AI boats and aerial drone.
        """
        templates = [
            {
                "sender": "AI-USV ALPHA",
                "receiver": "AI-USV BRAVO",
                "msg_type": "SWARM_SPEED_SYNC",
                "protocol": "M2M-MAVLink/STANAG-4586",
                "payload": "Sweep speed synchronized at 1.8 kts. Heading locked 048°. Boom catenary profile optimal.",
                "level": "INFO"
            },
            {
                "sender": "AI-USV BRAVO",
                "receiver": "AI-USV ALPHA",
                "msg_type": "BOOM_TENSION_ALERT",
                "protocol": "M2M-P2P-CAN",
                "payload": "Winch load cell: 39.1 kN. Aperture spacing 195m maintained. No skirt roll detected.",
                "level": "SUCCESS"
            },
            {
                "sender": "AI-USV CHARLIE",
                "receiver": "AI-USV ALPHA",
                "msg_type": "SKIMMER_INTAKE_COORDINATION",
                "protocol": "M2M-TELEMETRY",
                "payload": "Weir lip submerged 32mm in apex pocket. Hydro-viscous pump running @ 58.5 m³/h. Pure emulsion intake.",
                "level": "SUCCESS"
            },
            {
                "sender": "AI-UAV SENTRY",
                "receiver": "SWARM_BROADCAST",
                "msg_type": "SLICK_PERIMETER_VECTOR",
                "protocol": "M2M-UAV-MESH",
                "payload": "SAR FLIR edge lock: Heavy crude core bearing 052°, 310m ahead. Vectoring Alpha & Bravo +4° starboard.",
                "level": "WARNING"
            },
            {
                "sender": "AI-USV ALPHA",
                "receiver": "AI-USV CHARLIE",
                "msg_type": "FORMATION_CORRECTION",
                "protocol": "M2M-COLLISION-AVOID",
                "payload": "Acknowledged UAV vector. Adjusting starboard catenary angle. Charlie keep apex standoff 45m.",
                "level": "INFO"
            },
            {
                "sender": "AI-USV CHARLIE",
                "receiver": "COMMAND_STATION",
                "msg_type": "RECOVERY_PROGRESS",
                "protocol": "AIS-ASM/SAT-UPLINK",
                "payload": "Recovered 48.2 m³ (303 bbl). Internal emulsion hold 40.2% full. Estimated 3.4h to companion tanker offload.",
                "level": "INFO"
            }
        ]

        now = time.strftime("%H:%M:%S")
        messages = []
        for idx, t in enumerate(templates):
            # Stagger timestamps slightly
            sec_offset = (len(templates) - idx) * 3
            messages.append({
                "id": f"m2m-{int(time.time())}-{idx}",
                "timestamp": now,
                "sender": t["sender"],
                "receiver": t["receiver"],
                "msg_type": t["msg_type"],
                "protocol": t["protocol"],
                "text": t["payload"],
                "level": t["level"],
                "signal_dbm": random.randint(-62, -52),
                "mesh_latency_ms": round(random.uniform(11.2, 17.8), 1)
            })

        return messages

    def simulate_swarm_step(
        self,
        current_swarm: Dict[str, Any],
        step_seconds: float = 3.0
    ) -> Dict[str, Any]:
        """
        Advances the swarm simulation by a step: updates coordinates along drift,
        increments recovered crude, recalculates boom catenary, and adds a new M2M message.
        """
        boats = current_swarm.get("boats", [])
        if not boats:
            return current_swarm

        # Advance boats slightly along current heading
        drift_knots = 1.8
        deg_per_sec = (drift_knots * 0.514444) / 111000.0  # roughly in degrees latitude

        alpha = next((b for b in boats if b["id"] == "ai-usv-01"), None)
        bravo = next((b for b in boats if b["id"] == "ai-usv-02"), None)
        charlie = next((b for b in boats if b["id"] == "ai-usv-03"), None)
        uav = next((b for b in boats if b["id"] == "ai-uav-01"), None)

        if alpha and bravo and charlie:
            heading_rad = math.radians(alpha.get("heading", 45.0))
            delta_lat = deg_per_sec * step_seconds * math.cos(heading_rad)
            delta_lon = deg_per_sec * step_seconds * math.sin(heading_rad)

            for b in [alpha, bravo, charlie]:
                b["lat"] = round(b["lat"] + delta_lat, 6)
                b["lon"] = round(b["lon"] + delta_lon, 6)
                b["fuel_pct"] = max(5, round(b.get("fuel_pct", 90) - 0.02, 2))

            # UAV circles above
            if uav:
                uav_rad = math.radians(uav.get("heading", 60.0) + 15.0)
                uav["lat"] = round(uav["lat"] + 0.0003 * math.cos(uav_rad), 6)
                uav["lon"] = round(uav["lon"] + 0.0003 * math.sin(uav_rad), 6)
                uav["heading"] = (uav.get("heading", 60.0) + 5.0) % 360.0
                uav["battery_pct"] = max(10, round(uav.get("battery_pct", 80) - 0.04, 2))

            # Update boom catenary
            current_swarm["containment_boom"]["catenary_points"] = self._generate_boom_catenary(
                (alpha["lat"], alpha["lon"]),
                (bravo["lat"], bravo["lon"]),
                (charlie["lat"], charlie["lon"]),
                num_segments=16
            )

            # Update skimmer recovery accumulation
            # 58.5 m3/h -> m3 per step
            rate_m3s = 58.5 / 3600.0
            recovered_increment = round(rate_m3s * step_seconds, 3)
            charlie["payload"]["emulsion_recovered_m3"] = round(
                charlie["payload"]["emulsion_recovered_m3"] + recovered_increment, 2
            )
            charlie["payload"]["tank_fill_pct"] = min(100.0, round(
                (charlie["payload"]["emulsion_recovered_m3"] / charlie["payload"]["tank_capacity_m3"]) * 100.0, 1
            ))
            current_swarm["skimmer_operations"]["current_recovery_m3"] = charlie["payload"]["emulsion_recovered_m3"]

        return current_swarm

# Singleton instance
ai_swarm_engine = AISwarmFleetEngine()
