"""
Forensic PDF & JSON Evidence Dossier Generator
----------------------------------------------
Generates maritime authority investigation reports for oil spill attribution.
Uses ReportLab to produce formatted PDF documents with tables, metadata, and attribution evidence.
"""

import os
import io
import math
from datetime import datetime
from typing import Dict, Any, List
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)


class IncidentReportGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()

    def generate_pdf_bytes(
        self,
        scenario_data: Dict[str, Any],
        ranked_vessels: List[Dict[str, Any]],
        investigator_name: str = "Maritime Enforcement Officer"
    ) -> bytes:
        """
        Builds a multi-page/single-page forensic PDF dossier and returns bytes.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        elements = []

        # Color Palette
        navy = colors.HexColor("#0B1B3D")
        gold = colors.HexColor("#D97706")
        dark_gray = colors.HexColor("#1E293B")
        light_bg = colors.HexColor("#F8FAFC")

        # Custom Styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=self.styles["Heading1"],
            fontSize=18,
            leading=22,
            textColor=navy,
            spaceAfter=4
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=self.styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#475569"),
            spaceAfter=12
        )
        heading2_style = ParagraphStyle(
            "SectionHeading",
            parent=self.styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=navy,
            spaceBefore=10,
            spaceAfter=6
        )
        normal_style = ParagraphStyle(
            "NormalText",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=dark_gray
        )
        bold_style = ParagraphStyle(
            "BoldText",
            parent=self.styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=dark_gray,
            fontName="Helvetica-Bold"
        )

        # Header Title
        elements.append(Paragraph("OFFICIAL MARITIME FORENSIC ATTRIBUTION DOSSIER", title_style))
        elements.append(Paragraph(
            f"SIH26143 AI Satellite & AIS Correlation Engine | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Investigator: {investigator_name}",
            subtitle_style
        ))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=navy, spaceBefore=2, spaceAfter=10))

        # 1. Spill Incident Overview Table
        spill_info = scenario_data.get("spill", {})
        centroid = spill_info.get("centroid", {})
        
        area_val = float(spill_info.get("area_km2", 2.85))
        thick_val = float(spill_info.get("thickness_mm", 0.25))
        perim_val = float(spill_info.get("perimeter_km", round(2.3 * 2 * (3.14159 * area_val)**0.5, 2)))
        vol_m3 = round(area_val * thick_val * 1000.0, 1)
        vol_bbl = round(vol_m3 * 6.28981, 0)
        vol_tons = round(vol_m3 * 0.88, 1)
        skimmers = max(1, int(math.ceil(vol_m3 / 480.0)))
        tankers = max(1, int(math.ceil((vol_m3 * 1.35) / 1500.0)))
        boom_km = round(perim_val * 1.25, 1)

        overview_data = [
            [
                Paragraph("<b>Incident ID:</b>", normal_style),
                Paragraph(str(scenario_data.get("id", "SPILL-2026-05")), normal_style),
                Paragraph("<b>Satellite Sensor:</b>", normal_style),
                Paragraph(str(spill_info.get("sensor", "Sentinel-1 SAR (C-Band)")), normal_style),
            ],
            [
                Paragraph("<b>Detection Time:</b>", normal_style),
                Paragraph(str(spill_info.get("detection_time", "12 May 2026, 10:30 AM")), normal_style),
                Paragraph("<b>Confidence Level:</b>", normal_style),
                Paragraph(f"{int(spill_info.get('confidence', 0.92) * 100)}%", normal_style),
            ],
            [
                Paragraph("<b>Spill Centroid:</b>", normal_style),
                Paragraph(f"{centroid.get('lat', '13.052')}° N, {centroid.get('lon', '80.318')}° E", normal_style),
                Paragraph("<b>Estimated Area:</b>", normal_style),
                Paragraph(f"{area_val} km²", normal_style),
            ],
            [
                Paragraph("<b>Slick Perimeter:</b>", normal_style),
                Paragraph(f"{perim_val} km", normal_style),
                Paragraph("<b>Average Thickness:</b>", normal_style),
                Paragraph(f"{thick_val} mm (Bonn Code 5)", normal_style),
            ],
            [
                Paragraph("<b>Total Spill Volume:</b>", normal_style),
                Paragraph(f"<b>{vol_m3:,.1f} m³</b> ({vol_bbl:,.0f} bbl / {vol_tons:,.1f} MT)", normal_style),
                Paragraph("<b>Required Skimmers:</b>", normal_style),
                Paragraph(f"<b>{skimmers} High-Volume Skimmers</b>", normal_style),
            ],
            [
                Paragraph("<b>Oil Tankers Needed:</b>", normal_style),
                Paragraph(f"<b>{tankers} Storage Tanker(s)</b> (1,500 m³)", normal_style),
                Paragraph("<b>Containment Booms:</b>", normal_style),
                Paragraph(f"<b>{boom_km} km</b> ({int(boom_km*1000):,} m curtain)", normal_style),
            ],
            [
                Paragraph("<b>Sea Conditions:</b>", normal_style),
                Paragraph(f"Current: {scenario_data.get('drift_params', {}).get('current_speed_knots', 0.8)} kts @ {scenario_data.get('drift_params', {}).get('current_dir_deg', 45)}°", normal_style),
                Paragraph("<b>Surface Wind:</b>", normal_style),
                Paragraph(f"{scenario_data.get('drift_params', {}).get('wind_speed_knots', 12)} kts @ {scenario_data.get('drift_params', {}).get('wind_dir_deg', 60)}°", normal_style),
            ]
        ]

        overview_table = Table(overview_data, colWidths=[110, 160, 115, 155])
        overview_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), light_bg),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0, 0), (-1, -1), 3.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ]))
        elements.append(overview_table)
        elements.append(Spacer(1, 10))

        # 2. Top Ranked Suspect Vessels Table
        elements.append(Paragraph("Correlated Candidate Vessels (Ranked by Attribution Likelihood)", heading2_style))

        vessel_rows = [
            [
                Paragraph("<b>Rank</b>", bold_style),
                Paragraph("<b>Vessel Name</b>", bold_style),
                Paragraph("<b>MMSI</b>", bold_style),
                Paragraph("<b>Type</b>", bold_style),
                Paragraph("<b>CPA Dist</b>", bold_style),
                Paragraph("<b>Speed</b>", bold_style),
                Paragraph("<b>Score</b>", bold_style),
                Paragraph("<b>Likelihood</b>", bold_style)
            ]
        ]

        for v in ranked_vessels[:6]:
            lh = v.get("likelihood", "Low")
            lh_color = "#16A34A" if lh == "High" else ("#D97706" if lh == "Medium" else "#DC2626")
            lh_text = f'<font color="{lh_color}"><b>{lh}</b></font>'

            vessel_rows.append([
                Paragraph(str(v.get("rank", "-")), normal_style),
                Paragraph(str(v.get("vessel_name", "Unknown")), bold_style),
                Paragraph(str(v.get("mmsi", "-")), normal_style),
                Paragraph(str(v.get("vessel_type", "-")), normal_style),
                Paragraph(f"{v.get('cpa_km', '-')} km", normal_style),
                Paragraph(f"{v.get('avg_speed_knots', '-')} kts", normal_style),
                Paragraph(f"<b>{v.get('score', 0)}%</b>", bold_style),
                Paragraph(lh_text, normal_style)
            ])

        v_table = Table(vessel_rows, colWidths=[35, 110, 75, 95, 60, 55, 45, 65])
        v_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0B1B3D")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light_bg]),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (6, 0), (6, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(v_table)
        elements.append(Spacer(1, 14))

        # 3. Prime Suspect Forensic Breakdown
        if ranked_vessels:
            prime = ranked_vessels[0]
            elements.append(Paragraph(f"Primary Suspect Dossier: {prime.get('vessel_name')} (MMSI: {prime.get('mmsi')})", heading2_style))
            
            dossier_text = f"""
            <b>Attribution Score:</b> {prime.get('score')}% ({prime.get('likelihood')} Likelihood)<br/>
            <b>Vessel Classification:</b> {prime.get('vessel_type')} | <b>Last Seen:</b> {prime.get('time_at_cpa', 'N/A')}<br/>
            <b>Closest Point of Approach (CPA):</b> {prime.get('cpa_km')} km from the spill origin locus.<br/>
            <b>Course at CPA:</b> {prime.get('course_at_cpa', 'N/A')}° | <b>Average Speed:</b> {prime.get('avg_speed_knots', 'N/A')} knots
            """
            elements.append(Paragraph(dossier_text, normal_style))
            elements.append(Spacer(1, 6))

            elements.append(Paragraph("<b>Recorded Evidentiary Factors:</b>", bold_style))
            for ev in prime.get("evidence", []):
                elements.append(Paragraph(f"• {ev}", normal_style))

        elements.append(Spacer(1, 16))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94A3B8"), spaceBefore=6, spaceAfter=8))
        elements.append(Paragraph(
            "<b>Notice:</b> This forensic document is algorithmically compiled based on Sentinel-1 SAR satellite imagery "
            "and Terrestrial/Satellite AIS tracking telemetry. Intended for Port State Control inspection, Coast Guard interdiction, "
            "and environmental compliance proceedings.",
            ParagraphStyle("Disclaimer", parent=self.styles["Normal"], fontSize=7.5, leading=10, textColor=colors.HexColor("#64748B"))
        ))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
