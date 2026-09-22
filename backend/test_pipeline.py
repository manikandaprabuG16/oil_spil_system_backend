"""
Quick verification script for backend intelligence pipeline and PDF generation.
"""

from backend.app import load_scenario_json, analyze_scenario, report_gen

def test_pipeline():
    print("Testing scenario loading...")
    data = load_scenario_json("scenario-chennai-sih26143")
    print(f"Loaded scenario: {data['name']}, vessels: {len(data['vessels'])}")

    print("Testing pipeline analysis...")
    res = analyze_scenario(data)
    print("KPIs:", res["kpis"])
    print(f"Candidates ranked: {len(res['ranked_candidates'])}")
    for cand in res["ranked_candidates"][:4]:
        print(f"Rank {cand['rank']}: {cand['vessel_name']} ({cand['vessel_type']}) - Score: {cand['score']}% ({cand['likelihood']}), CPA: {cand['cpa_km']} km")

    print("Testing PDF Generation...")
    pdf_bytes = report_gen.generate_pdf_bytes(data, res["ranked_candidates"])
    print(f"PDF successfully generated: {len(pdf_bytes)} bytes")
    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_pipeline()
