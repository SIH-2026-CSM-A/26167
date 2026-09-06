"""Evidence report generators: PDF document and QGIS-compliant GeoJSON export."""

from __future__ import annotations

import io
import json
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.contracts.schemas import Answer, Evidence, TraceStep


def _get_query_id(answer: Answer) -> str:
    return getattr(answer, "query_id", None) or answer.trace.trace_id


def _build_header(styles: Any, query_id: str) -> list[Any]:
    return [
        Paragraph("<b>SatQuery AI — Evidentiary Report</b>", styles["Title"]),
        Spacer(1, 8),
        Paragraph(f"<b>Query / Trace ID:</b> {query_id}", styles["Normal"]),
        Spacer(1, 10),
    ]


def _build_summary_table(styles: Any, answer: Answer) -> list[Any]:
    verdict = "Abstained" if answer.abstained else "Verified"
    conf_str = f"{answer.confidence * 100:.1f}% ({answer.confidence:.2f})"
    text_content = answer.text
    if answer.abstained and answer.abstention_reason:
        text_content += f"\nAbstention Reason: {answer.abstention_reason}"
    rows = [
        ["Field", "Value"],
        ["Verdict", verdict],
        ["Confidence", conf_str],
        ["Assessment", Paragraph(text_content, styles["Normal"])],
    ]
    tbl = Table(rows, colWidths=[110, 430])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ]
        )
    )
    return [
        Paragraph("<b>Assessment Summary</b>", styles["Heading2"]),
        Spacer(1, 6),
        tbl,
        Spacer(1, 12),
    ]


def _build_citations_table(styles: Any, evidence_list: list[Evidence]) -> list[Any]:
    rows: list[list[Any]] = [["ID", "Tool", "Confidence", "Payload / Findings"]]
    for ev in evidence_list:
        conf_val = f"{ev.confidence * 100:.1f}% ({ev.confidence:.2f})"
        payload_desc = (
            str(ev.payload.get("description"))
            if "description" in ev.payload
            else json.dumps(ev.payload)
        )
        rows.append(
            [
                ev.id,
                ev.tool,
                conf_val,
                Paragraph(payload_desc[:250], styles["Normal"]),
            ]
        )
    if len(rows) == 1:
        rows.append(["-", "None", "N/A", "No verification citations recorded"])
    tbl = Table(rows, colWidths=[50, 95, 75, 320])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [
        Paragraph("<b>Verification Citations</b>", styles["Heading2"]),
        Spacer(1, 6),
        tbl,
        Spacer(1, 12),
    ]


def _build_trace_table(styles: Any, steps: list[TraceStep]) -> list[Any]:
    rows: list[list[Any]] = [["#", "Module", "Action", "Confidence", "Parameters"]]
    for idx, step in enumerate(steps, start=1):
        conf_str = f"{step.confidence * 100:.0f}%" if step.confidence is not None else "N/A"
        params_str = json.dumps(step.params) if step.params else "{}"
        rows.append(
            [
                str(idx),
                step.module,
                step.action,
                conf_str,
                Paragraph(params_str[:180], styles["Normal"]),
            ]
        )
    if len(rows) == 1:
        rows.append(["-", "None", "None", "N/A", "No trace steps recorded"])
    tbl = Table(rows, colWidths=[24, 90, 86, 60, 280])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [
        Paragraph("<b>Execution Trace</b>", styles["Heading2"]),
        Spacer(1, 6),
        tbl,
        Spacer(1, 12),
    ]


def _build_disclaimers(styles: Any) -> list[Any]:
    disclaimer_text = (
        "<b>Methodology Disclaimer:</b> Automated interpretation provided by SatQuery AI is an "
        "evidentiary decision-support aid and should not replace expert human analysis for "
        "critical decisions. Findings are generated using cross-modal neural models."
    )
    f13_text = (
        "<b>BigEarthNet.txt Adaptation Note (F13):</b> Multi-label land-cover classifications "
        "and semantic feature hierarchies are mapped against the BigEarthNet taxonomy "
        "(reference F13) for standardized satellite imagery understanding."
    )
    return [
        Spacer(1, 6),
        Paragraph(disclaimer_text, styles["Normal"]),
        Spacer(1, 6),
        Paragraph(f13_text, styles["Normal"]),
    ]


def generate_evidence_pdf(answer: Answer) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    query_id = _get_query_id(answer)
    elements: list[Any] = []
    elements.extend(_build_header(styles, query_id))
    elements.extend(_build_summary_table(styles, answer))
    elements.extend(_build_citations_table(styles, answer.evidence))
    elements.extend(_build_trace_table(styles, answer.trace.steps))
    elements.extend(_build_disclaimers(styles))
    doc.build(elements)
    buffer.seek(0)
    return buffer


def _extract_geometry(payload: dict[str, Any]) -> dict[str, Any]:
    if "geojson" in payload and isinstance(payload["geojson"], dict):
        geo = payload["geojson"]
        if geo.get("type") in ("Point", "Polygon", "MultiPolygon", "LineString", "MultiPoint"):
            return geo
        if "geometry" in geo and isinstance(geo["geometry"], dict):
            return geo["geometry"]
    if "geometry" in payload and isinstance(payload["geometry"], dict):
        return payload["geometry"]
    if (
        "bbox" in payload
        and isinstance(payload["bbox"], (list, tuple))
        and len(payload["bbox"]) == 4
    ):
        min_x, min_y, max_x, max_y = [float(v) for v in payload["bbox"]]
        return {
            "type": "Polygon",
            "coordinates": [
                [
                    [min_x, min_y],
                    [max_x, min_y],
                    [max_x, max_y],
                    [min_x, max_y],
                    [min_x, min_y],
                ]
            ],
        }
    return {"type": "Point", "coordinates": [0.0, 0.0]}


def _build_feature(ev: Evidence) -> dict[str, Any]:
    geometry = _extract_geometry(ev.payload)
    properties: dict[str, Any] = {
        "evidence_id": ev.id,
        "tool": ev.tool,
        "type": str(ev.type),
        "confidence": ev.confidence,
        "timing": ev.timing,
    }
    for key, val in ev.payload.items():
        if key not in ("geojson", "geometry"):
            properties[key] = val if isinstance(val, (str, int, float, bool)) else json.dumps(val)
    return {
        "type": "Feature",
        "id": ev.id,
        "geometry": geometry,
        "properties": properties,
    }


def generate_evidence_geojson(answer: Answer) -> tuple[str, str]:
    query_id = _get_query_id(answer)
    features = [_build_feature(ev) for ev in answer.evidence]
    if not features:
        features.append(
            {
                "type": "Feature",
                "id": f"{query_id}-summary",
                "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
                "properties": {
                    "query_id": query_id,
                    "confidence": answer.confidence,
                    "abstained": answer.abstained,
                    "text": answer.text,
                },
            }
        )
    collection = {
        "type": "FeatureCollection",
        "crs": {
            "type": "name",
            "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"},
        },
        "features": features,
    }
    filename = f"evidence-{query_id}.geojson"
    return json.dumps(collection, indent=2), filename
