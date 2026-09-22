"""
Oil Spill Intelligence System - FastAPI Backend
------------------------------------------------
Provides REST APIs for:
- Scenario management (Chennai SIH26143, Mumbai High)
- SAR & Optical AI Spill Detection
- Dynamic AIS correlation & drift backtracking
- Multi-criteria Attribution & Ranking Engine
- Automated Forensic PDF Report Generation
- Static frontend serving
"""

import os
import json
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .modules.sar_detector import SARSpillDetector
from .modules.ais_engine import AISEngine, haversine_distance_km
from .modules.drift_model import DriftModel
from .modules.correlation_engine import CorrelationEngine
from .modules.attribution_ranker import AttributionRanker
from .modules.report_generator import IncidentReportGenerator
from .modules.ai_swarm_engine import ai_swarm_engine
from .modules.auth import (
    verify_credentials,
    create_session,
    validate_session,
    lock_session,
    unlock_session,
    terminate_session,
    LoginRequest,
    UnlockRequest,
    TokenRequest,
    AUTHORIZED_OPERATOR_ID,
    SESSION_DURATION_SECONDS
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "sample_data")
FRONTEND_DIR = os.path.join(os.path.dirname(BASE_DIR), "frontend")

app = FastAPI(
    title="SIH26143 Oil Spill Attribution Intelligence System",
    description="Satellite Imagery + AIS Vessel Movement Correlation & Attribution Platform",
    version="1.0.0"
)

# Configure CORS for Vercel Frontend & Local Development
ALLOWED_ORIGINS = [
    "https://oil-spil-system-frontend.vercel.app",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://localhost:5173",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sar_detector = SARSpillDetector()
ais_engine = AISEngine()
drift_model = DriftModel()
correlation_engine = CorrelationEngine()
attribution_ranker = AttributionRanker()
report_gen = IncidentReportGenerator()


def load_scenario_json(scenario_id: str) -> Dict[str, Any]:
    # Check direct filename or map id
    filename = f"{scenario_id}.json" if not scenario_id.endswith(".json") else scenario_id
    if "chennai" in scenario_id:
        filename = "scenario_chennai.json"
    elif "mumbai" in scenario_id:
        filename = "scenario_mumbai_high.json"

    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_scenario(scenario_data: Dict[str, Any], custom_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Runs the full end-to-end intelligence pipeline on scenario data.
    """
    spill = dict(scenario_data["spill"])
    centroid = spill["centroid"]
    detect_time = spill["detection_timestamp"]
    drift_params = scenario_data.get("drift_params", {})

    area_km2 = float(spill.get("area_km2", 2.85))
    if custom_params:
        cur_speed = float(custom_params.get("current_speed_knots", drift_params.get("current_speed_knots", 0.8)))
        cur_dir = float(custom_params.get("current_dir_deg", drift_params.get("current_dir_deg", 45.0)))
        wind_speed = float(custom_params.get("wind_speed_knots", drift_params.get("wind_speed_knots", 12.0)))
        wind_dir = float(custom_params.get("wind_dir_deg", drift_params.get("wind_dir_deg", 60.0)))
        radius_km = float(custom_params.get("radius_km", 25.0))
        hours_back = float(custom_params.get("hours_back", 4.0))
        thickness_mm = float(custom_params.get("thickness_mm", spill.get("thickness_mm", 0.25)))
        recovery_window_hours = float(custom_params.get("recovery_window_hours", 48.0))
    else:
        cur_speed = drift_params.get("current_speed_knots", 0.8)
        cur_dir = drift_params.get("current_dir_deg", 45.0)
        wind_speed = drift_params.get("wind_speed_knots", 12.0)
        wind_dir = drift_params.get("wind_dir_deg", 60.0)
        radius_km = 25.0
        hours_back = 4.0
        thickness_mm = float(spill.get("thickness_mm", 0.25))
        recovery_window_hours = 48.0

    # Calculate slick perimeter from polygon geometry
    perimeter_km = drift_model.calculate_polygon_perimeter_km(spill.get("polygon", []), area_km2)
    spill["perimeter_km"] = perimeter_km
    spill["thickness_mm"] = thickness_mm

    # Calculate overall oil volume and cleanup resource requirements
    equipment = drift_model.calculate_oil_spill_volume_and_resources(
        area_km2=area_km2,
        perimeter_km=perimeter_km,
        thickness_mm=thickness_mm,
        recovery_window_hours=recovery_window_hours
    )
    spill["volume_m3"] = equipment["volume_m3"]
    spill["volume_bbl"] = equipment["volume_bbl"]
    spill["volume_tons"] = equipment["volume_tons"]
    spill["equipment"] = equipment

    # 1. Backtrack spill origin using drift modeling
    backtrack_points = drift_model.backtrack_spill_origin(
        spill_lat=centroid["lat"],
        spill_lon=centroid["lon"],
        detect_time=detect_time,
        hours_back=hours_back,
        current_speed_knots=cur_speed,
        current_direction_deg=cur_dir,
        wind_speed_knots=wind_speed,
        wind_direction_deg=wind_dir
    )

    # 1b. Forecast forward slick drift (+6h, +12h, +24h, +48h, +72h)
    spill_forecasts = drift_model.forecast_spill_forward(
        spill_lat=centroid["lat"],
        spill_lon=centroid["lon"],
        polygon=spill.get("polygon", []),
        initial_area_km2=area_km2,
        detect_time=detect_time,
        current_speed_knots=cur_speed,
        current_direction_deg=cur_dir,
        wind_speed_knots=wind_speed,
        wind_direction_deg=wind_dir,
        thickness_mm=thickness_mm
    )

    # 2. Spatio-temporal filtering of all AIS vessels
    all_vessels = scenario_data.get("vessels", [])
    filtered_vessels, total_evaluated = ais_engine.filter_spatio_temporal(
        vessels=all_vessels,
        spill_lat=centroid["lat"],
        spill_lon=centroid["lon"],
        spill_time=detect_time,
        radius_km=radius_km,
        time_window_hours_before=hours_back,
        time_window_hours_after=1.0
    )

    # 3. Geometric & temporal trajectory correlation
    correlations = []
    for v in filtered_vessels:
        corr = correlation_engine.correlate_vessel_with_spill(
            vessel=v,
            spill_centroid=centroid,
            spill_polygon_coords=spill.get("polygon", []),
            backtrack_points=backtrack_points
        )
        correlations.append(corr)

    # 4. Multi-criteria scoring & ranking
    ranked_candidates = attribution_ranker.rank_candidates(correlations)

    # Attach full filtered tracks with interpolation for map visualization
    for cand in ranked_candidates:
        mmsi = cand["mmsi"]
        original_vessel = next((v for v in filtered_vessels if v["mmsi"] == mmsi), None)
        if original_vessel:
            cand["track"] = original_vessel.get("filtered_track", original_vessel.get("track", []))
            cand["flag"] = original_vessel.get("flag", "Unknown")
            cand["length"] = original_vessel.get("length", 0)
            cand["width"] = original_vessel.get("width", 0)
            cand["draught"] = original_vessel.get("draught", 0)
            cand["destination"] = original_vessel.get("destination", "Open Sea")

    # Prepare complete all_vessels list with full metadata, status and tracks for complete corridor visualization
    ranked_map = {c["mmsi"]: c for c in ranked_candidates}
    all_vessels_enriched = []
    for v in all_vessels:
        mmsi = v["mmsi"]
        v_dict = dict(v)
        if mmsi in ranked_map:
            v_dict.update(ranked_map[mmsi])
        else:
            v_track = v.get("track", [])
            min_dist = 999.0
            if v_track:
                for pt in v_track:
                    d = haversine_distance_km(centroid["lat"], centroid["lon"], pt["lat"], pt["lon"])
                    if d < min_dist:
                        min_dist = d
            else:
                min_dist = 35.0
            v_dict["rank"] = len(ranked_candidates) + 1
            v_dict["score"] = 5
            v_dict["likelihood"] = "Negligible"
            v_dict["badge_class"] = "low"
            v_dict["cpa_km"] = round(min_dist, 1)
            v_dict["avg_speed_knots"] = round(sum(p.get("sog", 12.0) for p in v_track) / max(len(v_track), 1), 1) if v_track else 12.0
            v_dict["evidence"] = ["Transited outside critical spill temporal/spatial containment window."]
            v_dict["time_at_cpa"] = v_track[-1]["timestamp"] if v_track else detect_time
        all_vessels_enriched.append(v_dict)

    # 4. Generate Coordinated AI Autonomous Response Swarm (Booms + Skimmers + M2M Comms)
    ai_swarm = ai_swarm_engine.initialize_swarm_for_spill(
        centroid_lat=centroid["lat"],
        centroid_lon=centroid["lon"],
        spill_area_km2=area_km2,
        perimeter_km=perimeter_km,
        thickness_mm=thickness_mm,
        wind_dir_deg=wind_dir,
        current_dir_deg=cur_speed
    )

    return {
        "scenario_info": {
            "id": scenario_data.get("id"),
            "name": scenario_data.get("name"),
            "location_name": scenario_data.get("location_name"),
            "description": scenario_data.get("description")
        },
        "spill": spill,
        "backtrack_trajectory": backtrack_points,
        "forecasts": spill_forecasts,
        "ai_swarm": ai_swarm,
        "kpis": {
            "spill_detected": True,
            "spill_area_km2": area_km2,
            "spill_perimeter_km": perimeter_km,
            "spill_thickness_mm": thickness_mm,
            "spill_volume_m3": equipment["volume_m3"],
            "spill_volume_bbl": equipment["volume_bbl"],
            "spill_volume_tons": equipment["volume_tons"],
            "skimmers_needed": equipment["skimmers_needed"],
            "tankers_needed": equipment["tankers_needed"],
            "booms_needed_km": equipment["boom_length_km"],
            "observation_vessels_needed": equipment["observation_vessels_needed"],
            "detected_time": spill.get("detection_time", "10:30 AM 12 May 2026"),
            "location_display": f"{centroid['lat']}° N, {centroid['lon']}° E",
            "centroid": centroid,
            "total_vessels_analyzed": len(all_vessels),
            "candidate_count": len(ranked_candidates),
            "equipment": equipment
        },
        "ranked_candidates": ranked_candidates,
        "all_vessels": all_vessels_enriched,
        "drift_parameters_used": {
            "current_speed_knots": cur_speed,
            "current_dir_deg": cur_dir,
            "wind_speed_knots": wind_speed,
            "wind_dir_deg": wind_dir,
            "radius_km": radius_km,
            "hours_back": hours_back,
            "thickness_mm": thickness_mm,
            "recovery_window_hours": recovery_window_hours
        }
    }


# =================== API Endpoints ===================

# ----------------- Authentication & Session APIs -----------------
@app.post("/api/auth/login")
async def api_login(req: LoginRequest):
    if not verify_credentials(req.operator_id, req.password):
        raise HTTPException(
            status_code=401,
            detail="Invalid Maritime Security Credentials. Access denied."
        )
    return create_session(req.operator_id)


@app.post("/api/auth/verify")
async def api_verify(req: TokenRequest):
    result = validate_session(req.token)
    if not result["valid"]:
        raise HTTPException(status_code=401, detail=result.get("reason", "Session invalid"))
    return result


@app.post("/api/auth/lock")
async def api_lock(req: TokenRequest):
    result = lock_session(req.token)
    if not result.get("success", False):
        raise HTTPException(status_code=401, detail=result.get("reason", "Unauthorized lock attempt"))
    return result


@app.post("/api/auth/unlock")
async def api_unlock(req: UnlockRequest):
    result = unlock_session(req.token, req.password)
    if not result.get("success", False):
        raise HTTPException(status_code=401, detail=result.get("message", "Clearance failed"))
    return result


@app.post("/api/auth/logout")
async def api_logout():
    return terminate_session()


@app.get("/api/scenarios")
async def list_scenarios():
    return [
        {
            "id": "scenario-chennai-sih26143",
            "name": "SIH26143 - Bay of Bengal / Chennai Coast",
            "location": "13.052° N, 80.318° E",
            "area_km2": 2.85,
            "vessels": 32,
            "primary_suspect": "Vessel A (Tanker, 91% High)"
        },
        {
            "id": "scenario-mumbai-high",
            "name": "Mumbai High Corridor (Arabian Sea)",
            "location": "19.420° N, 71.310° E",
            "area_km2": 4.12,
            "vessels": 18,
            "primary_suspect": "Arabian Voyager (Crude Oil Tanker, 88% High)"
        }
    ]


@app.get("/api/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    raw_data = load_scenario_json(scenario_id)
    return analyze_scenario(raw_data)


class CorrelationRequest(BaseModel):
    scenario_id: str
    current_speed_knots: float = 0.8
    current_dir_deg: float = 45.0
    wind_speed_knots: float = 12.0
    wind_dir_deg: float = 60.0
    radius_km: float = 25.0
    hours_back: float = 4.0
    thickness_mm: float = 0.25
    recovery_window_hours: float = 48.0


@app.post("/api/correlate")
async def re_correlate(req: CorrelationRequest):
    raw_data = load_scenario_json(req.scenario_id)
    custom_params = {
        "current_speed_knots": req.current_speed_knots,
        "current_dir_deg": req.current_dir_deg,
        "wind_speed_knots": req.wind_speed_knots,
        "wind_dir_deg": req.wind_dir_deg,
        "radius_km": req.radius_km,
        "hours_back": req.hours_back,
        "thickness_mm": req.thickness_mm,
        "recovery_window_hours": req.recovery_window_hours
    }
    return analyze_scenario(raw_data, custom_params)


class ResourceCalculationRequest(BaseModel):
    area_km2: float
    perimeter_km: Optional[float] = None
    thickness_mm: float = 0.25
    recovery_window_hours: float = 48.0
    skimmer_capacity_m3h: float = 40.0
    tanker_capacity_m3: float = 1500.0


@app.post("/api/calculate-resources")
async def calculate_resources(req: ResourceCalculationRequest):
    perimeter = req.perimeter_km
    if perimeter is None or perimeter <= 0:
        perimeter = round(2.3 * 2 * (3.14159265 * req.area_km2) ** 0.5, 2)
    res = drift_model.calculate_oil_spill_volume_and_resources(
        area_km2=req.area_km2,
        perimeter_km=perimeter,
        thickness_mm=req.thickness_mm,
        recovery_window_hours=req.recovery_window_hours,
        skimmer_capacity_m3h=req.skimmer_capacity_m3h,
        tanker_capacity_m3=req.tanker_capacity_m3
    )
    return res


@app.post("/api/detect")
async def detect_spill_image(file: UploadFile = File(...), bounds: str = Form("{}")):
    try:
        geo_bounds = json.loads(bounds)
    except Exception:
        geo_bounds = {"north": 13.08, "south": 13.02, "east": 80.35, "west": 80.28}

    content = await file.read()
    detection = sar_detector.detect_spill(content, geo_bounds)
    return detection


@app.get("/api/reports/download/{scenario_id}")
async def download_report(scenario_id: str):
    raw_data = load_scenario_json(scenario_id)
    analysis = analyze_scenario(raw_data)
    
    pdf_bytes = report_gen.generate_pdf_bytes(
        scenario_data=raw_data,
        ranked_vessels=analysis["ranked_candidates"],
        investigator_name="Senior Marine Pollution Inspector"
    )

    filename = f"Oil_Spill_Attribution_Dossier_{scenario_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


class SwarmStepRequest(BaseModel):
    swarm_state: Dict[str, Any]
    step_seconds: float = 3.0


@app.get("/api/ai-swarm/{scenario_id}")
async def get_ai_swarm(scenario_id: str):
    raw_data = load_scenario_json(scenario_id)
    analysis = analyze_scenario(raw_data)
    return analysis.get("ai_swarm", {})


@app.post("/api/ai-swarm/step")
async def step_ai_swarm(req: SwarmStepRequest):
    updated = ai_swarm_engine.simulate_swarm_step(req.swarm_state, req.step_seconds)
    # Also generate fresh M2M transmissions on each step
    boats = updated.get("boats", [])
    if boats:
        new_msgs = ai_swarm_engine.generate_m2m_transmissions(boats)
        updated["recent_transmissions"] = new_msgs
    return updated


@app.get("/api/risk-analysis/{scenario_id}")
async def get_risk_analysis(scenario_id: str):
    raw_data = load_scenario_json(scenario_id)
    analysis = analyze_scenario(raw_data)
    spill = analysis.get("spill", {})
    centroid = spill.get("centroid", {"lat": 13.052, "lon": 80.318})
    equipment = spill.get("equipment", {})

    sensitive_areas = [
        {
            "id": "coastal_north",
            "name": "Coastal Area (North)",
            "risk_level": "Very High",
            "badge_color": "#e53e3e",
            "distance_km": 4.2,
            "center": {"lat": round(centroid["lat"] + 0.04, 3), "lon": round(centroid["lon"] - 0.03, 3)},
            "radius_m": 3500
        },
        {
            "id": "fishing_zone_a",
            "name": "Fishing Zone A",
            "risk_level": "High",
            "badge_color": "#dd6b20",
            "distance_km": 7.8,
            "center": {"lat": round(centroid["lat"] - 0.03, 3), "lon": round(centroid["lon"] + 0.04, 3)},
            "radius_m": 4200
        },
        {
            "id": "marine_sanctuary",
            "name": "Marine Sanctuary",
            "risk_level": "High",
            "badge_color": "#dd6b20",
            "distance_km": 11.5,
            "center": {"lat": round(centroid["lat"] - 0.06, 3), "lon": round(centroid["lon"] + 0.07, 3)},
            "radius_m": 5000
        },
        {
            "id": "port_area",
            "name": "Port Area",
            "risk_level": "Medium",
            "badge_color": "#d97706",
            "distance_km": 14.2,
            "center": {"lat": round(centroid["lat"] + 0.08, 3), "lon": round(centroid["lon"] - 0.02, 3)},
            "radius_m": 6000
        }
    ]

    response_recommendations = [
        {
            "title": f"Deploy Containment Booms ({equipment.get('boom_length_km', 15.5)} km)",
            "priority": f"{equipment.get('boom_length_meters', 15500):,.0f}m Perimeter Encirclement",
            "badge_class": "badge-red",
            "icon": "boom"
        },
        {
            "title": f"Mobilize Skimmers ({equipment.get('skimmers_needed', 3)} Units)",
            "priority": f"High-Volume Offshore Skimmers ({equipment.get('recovery_window_hours', 48)}h target)",
            "badge_class": "badge-orange",
            "icon": "ship"
        },
        {
            "title": f"Deploy Oil Tankers ({equipment.get('tankers_needed', 1)} Vessel)",
            "priority": f"Temporary Emulsion Storage ({equipment.get('total_fluid_emulsion_m3', 960)} m³)",
            "badge_class": "badge-orange",
            "icon": "ship"
        },
        {
            "title": f"Aerial & Sea Observation ({equipment.get('observation_vessels_needed', 2)} Patrols)",
            "priority": f"{equipment.get('surveillance_drones_needed', 1)} Drone + {equipment.get('observation_vessels_needed', 2)} Patrol Craft",
            "badge_class": "badge-yellow",
            "icon": "helicopter"
        },
        {
            "title": "On-Site Monitoring & Hydrodynamic Tracking",
            "priority": "Real-Time Drift Alignment",
            "badge_class": "badge-green",
            "icon": "eye"
        }
    ]

    recommended_priorities = [
        f"Priority 1: Encircle {equipment.get('perimeter_km', 12.4)} km slick perimeter with {equipment.get('boom_length_km', 15.5)} km containment booms",
        f"Priority 2: Mobilize {equipment.get('skimmers_needed', 3)} offshore skimmers for {equipment.get('volume_m3', 712.5)} m³ ({equipment.get('volume_bbl', 4481.5)} bbl) crude recovery",
        f"Priority 3: Stage {equipment.get('tankers_needed', 1)} recovery tanker ({equipment.get('total_fluid_emulsion_m3', 960)} m³ capacity) at slick perimeter",
        f"Priority 4: Maintain continuous {equipment.get('observation_vessels_needed', 2)} patrol crafts + satellite monitoring along predicted drift"
    ]

    historical_risk = {
        "risk_level": "High Risk Zone",
        "past_incidents_5yr": 14,
        "vessel_density_daily": 142,
        "vulnerability_score": "8.4 / 10",
        "description": "High-risk zones based on past oil spill incidents and vessel density."
    }

    return {
        "scenario_id": scenario_id,
        "sensitive_areas": sensitive_areas,
        "response_recommendations": response_recommendations,
        "recommended_priorities": recommended_priorities,
        "historical_risk": historical_risk,
        "fleet_allocation": equipment
    }



# Serve pre-generated SAR images
SAR_IMG_DIR = os.path.join(DATA_DIR, "sar_images")
if os.path.exists(SAR_IMG_DIR):
    app.mount("/sar_images", StaticFiles(directory=SAR_IMG_DIR), name="sar_images")

# Serve Login Page
@app.get("/login")
@app.get("/login.html")
async def serve_login():
    login_path = os.path.join(FRONTEND_DIR, "login.html")
    if os.path.exists(login_path):
        return FileResponse(login_path)
    raise HTTPException(status_code=404, detail="Login page not found")


# Serve Frontend static assets
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
