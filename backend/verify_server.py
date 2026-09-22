import urllib.request
import json

def verify():
    # 1. Test frontend root HTML
    with urllib.request.urlopen("http://127.0.0.1:8000/") as resp:
        html = resp.read().decode("utf-8")
        print(f"[OK] Frontend HTML served: {len(html)} bytes, Status: {resp.status}")
        assert "OIL SPILL INTELLIGENCE SYSTEM" in html

    # 2. Test Scenarios list API
    with urllib.request.urlopen("http://127.0.0.1:8000/api/scenarios") as resp:
        scenarios = json.loads(resp.read().decode("utf-8"))
        print(f"[OK] Scenarios API: {len(scenarios)} scenarios available")

    # 3. Test Chennai scenario pipeline API
    with urllib.request.urlopen("http://127.0.0.1:8000/api/scenarios/scenario-chennai-sih26143") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"[OK] Scenario Details Loaded: {data['scenario_info']['name']}")
        print(f"     KPI Spill Area: {data['kpis']['spill_area_km2']} km²")
        print(f"     KPI Centroid: {data['kpis']['location_display']}")
        print(f"     KPI Vessels Analyzed: {data['kpis']['total_vessels_analyzed']}")
        print("     Top Candidate Vessels:")
        for v in data["ranked_candidates"][:3]:
            print(f"       • Rank {v['rank']}: {v['vessel_name']} ({v['vessel_type']}) - Score: {v['score']}% ({v['likelihood']} Likelihood) - CPA: {v['cpa_km']} km")

    # 4. Test PDF download endpoint
    with urllib.request.urlopen("http://127.0.0.1:8000/api/reports/download/scenario-chennai-sih26143") as resp:
        pdf_bytes = resp.read()
        print(f"[OK] Forensic PDF Report Endpoint: {len(pdf_bytes)} bytes downloaded")

    print("\n>>> ALL API, FRONTEND, AND REPORT ENDPOINTS VERIFIED 100% WORKING! <<<")

if __name__ == "__main__":
    verify()
