"""
Generates sample AIS CSV matching MarineCadastre / AISHub international maritime standard.
"""

import os
import json
import csv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "sample_data")

def generate_csv():
    with open(os.path.join(DATA_DIR, "scenario_chennai.json"), "r") as f:
        data = json.load(f)

    csv_path = os.path.join(DATA_DIR, "sample_ais_bay_of_bengal.csv")
    fieldnames = [
        "MMSI", "BaseDateTime", "LAT", "LON", "SOG", "COG", "Heading",
        "VesselName", "VesselType", "Flag", "Destination"
    ]

    all_rows = []
    for v in data["vessels"]:
        mmsi = v["mmsi"]
        name = v["vessel_name"]
        v_type = v["vessel_type"]
        flag = v.get("flag", "International")
        dest = v.get("destination", "Port")

        for ping in v.get("track", []):
            all_rows.append({
                "MMSI": mmsi,
                "BaseDateTime": ping["timestamp"],
                "LAT": ping["lat"],
                "LON": ping["lon"],
                "SOG": ping.get("sog", 0.0),
                "COG": ping.get("cog", 0.0),
                "Heading": ping.get("heading", ping.get("cog", 0.0)),
                "VesselName": name,
                "VesselType": v_type,
                "Flag": flag,
                "Destination": dest
            })

    # Sort chronologically
    all_rows.sort(key=lambda r: r["BaseDateTime"])

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Generated sample AIS CSV with {len(all_rows)} pings at: {csv_path}")

if __name__ == "__main__":
    generate_csv()
