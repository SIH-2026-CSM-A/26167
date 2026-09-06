import io
from typing import Any, Dict, List
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _build_header(styles: Any, query_id: str) -> List[Any]:
    elements: List[Any] = []
    elements.append(Paragraph("<b>SatQuery Evidence Report</b>", styles["Title"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Query ID:</b> {query_id}", styles["Normal"]))
    elements.append(Spacer(1, 12))
    return elements


def _build_summary_table(styles: Any, data: Dict[str, Any]) -> List[Any]:
    elements: List[Any] = []
    elements.append(Paragraph("<b>Assessment Summary</b>", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    verdict = str(data.get("verdict", data.get("status", "N/A")))
    confidence = str(data.get("confidence", "N/A"))
    summary = str(data.get("summary", data.get("text", "No summary available")))
    summary_rows = [
        ["Field", "Value"],
        ["Verdict", verdict],
        ["Confidence", confidence],
        ["Summary", summary],
    ]
    tbl = Table(summary_rows, colWidths=[120, 360])
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ])
    )
    elements.append(tbl)
    elements.append(Spacer(1, 14))
    return elements


def _build_citations_table(styles: Any, citations: List[Dict[str, Any]]) -> List[Any]:
    elements: List[Any] = []
    elements.append(Paragraph("<b>Verification Citations</b>", styles["Heading2"]))
    elements.append(Spacer(1, 6))
    rows = [["ID", "Source", "Confidence", "Evidence Details"]]
    for item in citations:
        c_id = str(item.get("id", item.get("citation_id", "-")))
        src = str(item.get("source", "-"))
        conf = str(item.get("confidence", "-"))
        dtl = str(item.get("detail", item.get("text", "-")))
        rows.append([c_id, src, conf, dtl])
    if len(rows) == 1:
        rows.append(["-", "No citations recorded", "-", "-"])
    tbl = Table(rows, colWidths=[40, 100, 80, 260])
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ])
    )
    elements.append(tbl)
    return elements


def generate_evidence_pdf(evidence_data: Dict[str, Any]) -> io.BytesIO:
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
    elements: List[Any] = []
    query_id = str(evidence_data.get("query_id", "N/A"))
    elements.extend(_build_header(styles, query_id))
    elements.extend(_build_summary_table(styles, evidence_data))
    citations = evidence_data.get("citations", [])
    elements.extend(_build_citations_table(styles, citations))
    doc.build(elements)
    buffer.seek(0)
    return buffer
