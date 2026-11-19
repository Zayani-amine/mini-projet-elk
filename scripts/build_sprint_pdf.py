import argparse
import html
import pathlib
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    ListFlowable,
    ListItem,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def make_styles():
    base = getSampleStyleSheet()
    return {
        "cover": ParagraphStyle(
            "Cover", parent=base["Title"], fontSize=22, leading=28,
            alignment=TA_CENTER, spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontSize=10, leading=14,
            alignment=TA_CENTER, textColor=colors.HexColor("#4A5568"), spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "H1", parent=base["Heading1"], fontSize=14, leading=18, spaceBefore=14,
            spaceAfter=6, textColor=colors.HexColor("#1F3A5F"),
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontSize=11.5, leading=15, spaceBefore=10,
            spaceAfter=4, textColor=colors.HexColor("#2C5282"),
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontSize=9.5, leading=13.5, spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"], fontSize=9.5, leading=13, spaceAfter=2,
        ),
        "cell": ParagraphStyle(
            "Cell", parent=base["BodyText"], fontSize=8, leading=10, spaceAfter=0,
        ),
        "cell_header": ParagraphStyle(
            "CellHeader", parent=base["BodyText"], fontSize=8, leading=10,
            textColor=colors.white, spaceAfter=0,
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"], fontSize=8, leading=10,
            backColor=colors.HexColor("#F5F7FA"),
        ),
    }


def inline(text):
    value = html.escape(text.strip())
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)


def parse_markdown(text, styles):
    story = []
    lines = text.splitlines()
    index = 0
    title = None
    paragraph = []
    bullets = []
    table = []
    code = []

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            story.append(Paragraph("<br/>".join(inline(line) for line in paragraph), styles["body"]))
            paragraph = []

    def flush_bullets():
        nonlocal bullets
        if bullets:
            items = [ListItem(Paragraph(inline(item), styles["bullet"])) for item in bullets]
            story.append(ListFlowable(items, bulletType="bullet", leftIndent=12))
            story.append(Spacer(1, 4))
            bullets = []

    def flush_table():
        nonlocal table
        if not table:
            return
        rows = []
        for row in table:
            cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            rows.append(cells)
        if rows:
            width = A4[0] - 40 * mm
            columns = len(rows[0])
            data = []
            for number, row in enumerate(rows):
                style = styles["cell_header"] if number == 0 else styles["cell"]
                data.append([Paragraph(inline(cell), style) for cell in row])
            grid = Table(data, colWidths=[width / columns] * columns, repeatRows=1)
            grid.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(grid)
            story.append(Spacer(1, 6))
        table = []

    def flush_code():
        nonlocal code
        if code:
            story.append(Preformatted("\n".join(code), styles["code"]))
            story.append(Spacer(1, 6))
            code = []

    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_bullets()
            flush_table()
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            flush_bullets()
            flush_code()
            table.append(stripped)
            index += 1
            continue
        if not stripped:
            flush_paragraph()
            flush_bullets()
            flush_table()
            flush_code()
            index += 1
            continue
        if stripped.startswith("# "):
            flush_paragraph()
            flush_bullets()
            flush_table()
            flush_code()
            heading = stripped[2:].strip()
            if title is None:
                title = heading
                story.append(Paragraph(inline(heading), styles["cover"]))
                story.append(Paragraph(
                    "IT Business School — Zayani Mohamed Amine — Encadrant : Mohamed Najeh ISSAOUI",
                    styles["subtitle"],
                ))
                story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#1F3A5F")))
                story.append(Spacer(1, 10))
            else:
                story.append(Paragraph(inline(heading), styles["h1"]))
            index += 1
            continue
        if stripped.startswith("## "):
            flush_paragraph()
            flush_bullets()
            flush_table()
            flush_code()
            story.append(Paragraph(inline(stripped[3:]), styles["h1"]))
            index += 1
            continue
        if stripped.startswith("### "):
            flush_paragraph()
            flush_bullets()
            flush_table()
            flush_code()
            story.append(Paragraph(inline(stripped[4:]), styles["h2"]))
            index += 1
            continue
        if stripped.startswith("- ") or stripped.startswith("* "):
            flush_paragraph()
            flush_table()
            flush_code()
            bullets.append(stripped[2:].strip())
            index += 1
            continue
        flush_bullets()
        flush_table()
        flush_code()
        paragraph.append(stripped)
        index += 1

    flush_paragraph()
    flush_bullets()
    flush_table()
    flush_code()
    return story, title


def add_page(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#718096"))
    canvas.drawString(20 * mm, 12 * mm, "Mini-Projet ELK — Smart Building IoT")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, "Page %d" % doc.page)
    canvas.restoreState()


def main():
    parser = argparse.ArgumentParser(description="Build a sprint PDF from a local Markdown draft.")
    parser.add_argument("markdown")
    parser.add_argument("output")
    args = parser.parse_args()
    source = pathlib.Path(args.markdown)
    target = pathlib.Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = make_styles()
    story, title = parse_markdown(source.read_text(encoding="utf-8"), styles)
    document = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=title or "Mini-Projet ELK",
        author="Zayani Mohamed Amine",
    )
    document.build(story, onFirstPage=add_page, onLaterPages=add_page)
    print("PDF_WRITTEN %s" % target)


if __name__ == "__main__":
    main()
