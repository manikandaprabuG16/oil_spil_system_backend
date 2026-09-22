import urllib.request
import json

def run_tests():
    print("=== 1. Testing Scenarios API ===")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/scenarios") as resp:
        scenarios = json.loads(resp.read().decode("utf-8"))
        print(f"Scenarios count: {len(scenarios)}")

    print("\n=== 2. Testing Chennai Scenario ===")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/scenarios/scenario-chennai-sih26143") as resp:
        ch = json.loads(resp.read().decode("utf-8"))
        k = ch["kpis"]
        print(f"Spill Area: {k.get('spill_area_km2')} km²")
        print(f"Perimeter: {k.get('spill_perimeter_km')} km")
        print(f"Thickness: {k.get('spill_thickness_mm')} mm")
        print(f"Volume: {k.get('spill_volume_m3')} m³ ({k.get('spill_volume_bbl')} bbl / {k.get('spill_volume_tons')} MT)")
        print(f"Skimmers Needed: {k.get('skimmers_needed')} units")
        print(f"Tankers Needed: {k.get('tankers_needed')} vessel(s)")
        print(f"Booms Needed: {k.get('booms_needed_km')} km")
        print(f"Forecasts count: {len(ch.get('forecasts', []))}")

    print("\n=== 3. Testing Mumbai High Scenario ===")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/scenarios/scenario-mumbai-high") as resp:
        mh = json.loads(resp.read().decode("utf-8"))
        k2 = mh["kpis"]
        print(f"Spill Area: {k2.get('spill_area_km2')} km²")
        print(f"Perimeter: {k2.get('spill_perimeter_km')} km")
        print(f"Thickness: {k2.get('spill_thickness_mm')} mm")
        print(f"Volume: {k2.get('spill_volume_m3')} m³ ({k2.get('spill_volume_bbl')} bbl / {k2.get('spill_volume_tons')} MT)")
        print(f"Skimmers Needed: {k2.get('skimmers_needed')} units")
        print(f"Tankers Needed: {k2.get('tankers_needed')} vessel(s)")

    print("\n=== 4. Testing Resource Calculation Endpoint ===")
    payload = {
        "area_km2": 5.0,
        "perimeter_km": 15.0,
        "thickness_mm": 0.50,
        "recovery_window_hours": 36.0,
        "skimmer_capacity_m3h": 60.0,
        "tanker_capacity_m3": 2000.0
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/calculate-resources",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        print(f"Calc Result: Area={res['area_km2']} km², Thickness={res['thickness_mm']} mm -> Volume={res['volume_m3']} m³, Skimmers={res['skimmers_needed']}, Tankers={res['tankers_needed']}, Booms={res['boom_length_km']} km")

    print("\n=== 5. Testing Risk Analysis Fleet Endpoint ===")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/risk-analysis/scenario-chennai-sih26143") as resp:
        ra = json.loads(resp.read().decode("utf-8"))
        print(f"Fleet allocation returned: {ra.get('fleet_allocation') is not None}")
        print("Response recommendations count:", len(ra.get("response_recommendations", [])))
        for r in ra.get("response_recommendations", []):
            print(f" - {r['title']} [{r['priority']}]")

    print("\n=== 6. Testing PDF Dossier Download ===")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/reports/download/scenario-chennai-sih26143") as resp:
        pdf_data = resp.read()
        print(f"PDF Download: {len(pdf_data)} bytes received (Status 200 OK)")

    print("\n=== ALL INTEGRATION TESTS PASSED! ===")

if __name__ == "__main__":
    run_tests()
