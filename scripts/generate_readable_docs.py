from __future__ import annotations

import ast
import html
import re
from pathlib import Path

from pygments import lex
from pygments.lexers import get_lexer_for_filename
from pygments.token import Comment, Keyword, Literal, Name, Number, Operator, String, Token
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"

PAGE_W = 1684
PAGE_H = 1191
MARGIN = 48
TITLE_H = 84
FOOTER_H = 36
CODE_X = 340
CODE_Y_TOP = PAGE_H - MARGIN - TITLE_H
CODE_W = 1004
CODE_H = PAGE_H - (MARGIN * 2) - TITLE_H - FOOTER_H
LEFT_X = MARGIN
RIGHT_X = CODE_X + CODE_W + 42
CALLOUT_W = 250
LINE_NO_W = 48
CODE_PAD_X = 16
CODE_PAD_Y = 16
FONT_NAME = "Courier"
FONT_BOLD = "Helvetica-Bold"
FONT_TEXT = "Helvetica"
CODE_FONT_SIZE = 10.5
LINE_H = 15.5
MAX_CODE_CHARS = 140
LINES_PER_PAGE = int((CODE_H - CODE_PAD_Y * 2) / LINE_H)

SOURCE_FILES = [
    "main.py",
    "pyproject.toml",
    ".gitignore",
    "Backend/api.py",
    "Backend/model_policy.py",
    "Backend/output.py",
    "Backend/pipeline.py",
    "Backend/extractors/document_classification.py",
    "Backend/extractors/field_mapper.py",
    "Backend/extractors/validation.py",
    "Backend/processors/docx_processor.py",
    "Backend/processors/image_processor.py",
    "Backend/processors/pdf_processor.py",
    "Backend/processors/text_extractor.py",
    "frontend/index.html",
    "frontend/package.json",
    "frontend/vite.config.js",
    "frontend/src/api.js",
    "frontend/src/App.jsx",
    "frontend/src/main.jsx",
    "frontend/src/styles.css",
    "testing/reporting.py",
    "testing/testing.py",
    "testing/test-CLI/test_cli_and_pipeline.py",
    "testing/test-CLI/test_invoice_pipeline.py",
]

TOKEN_COLORS = {
    Keyword: colors.HexColor("#d14a00"),
    Name.Function: colors.HexColor("#265aa5"),
    Name.Class: colors.HexColor("#7a3cb2"),
    Name.Builtin: colors.HexColor("#265aa5"),
    String: colors.HexColor("#198038"),
    Number: colors.HexColor("#8a4b08"),
    Literal: colors.HexColor("#198038"),
    Comment: colors.HexColor("#c62828"),
    Operator: colors.HexColor("#555555"),
    Token.Punctuation: colors.HexColor("#555555"),
}


def output_name(relative_path: str) -> str:
    safe = relative_path.replace("/", "__").replace(".", "_")
    return f"{safe}.pdf"


def color_for_token(token_type):
    for parent, color in TOKEN_COLORS.items():
        if token_type in parent:
            return color
    return colors.HexColor("#111111")


def draw_wrapped_text(c, text, x, y, width, size=15, leading=18, font=FONT_TEXT, fill=colors.black):
    c.setFillColor(fill)
    c.setFont(font, size)
    words = str(text).split()
    lines = []
    current = []
    for word in words:
        candidate = " ".join([*current, word])
        if stringWidth(candidate, font, size) <= width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def draw_arrow(c, start_x, start_y, end_x, end_y):
    c.setStrokeColor(colors.HexColor("#666666"))
    c.setLineWidth(1.25)
    c.line(start_x, start_y, end_x, end_y)
    angle_dx = -1 if start_x < end_x else 1
    c.line(end_x, end_y, end_x - 10 * angle_dx, end_y + 5)
    c.line(end_x, end_y, end_x - 10 * angle_dx, end_y - 5)


def summarize_python(path, lines):
    callouts = []
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        tree = None

    import_line = next((i for i, line in enumerate(lines, 1) if line.startswith(("import ", "from "))), None)
    if import_line:
        callouts.append((import_line, "Imports: these load framework, OCR, file, and helper modules used later."))

    if tree:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                doc = ast.get_docstring(node)
                if doc:
                    text = doc.splitlines()[0]
                elif node.name.startswith(("extract", "process", "classify", "validate", "map")):
                    text = f"`{node.name}` holds the core document-processing step for this file."
                elif node.name.startswith(("get", "load", "read")):
                    text = f"`{node.name}` reads or prepares data for the pipeline."
                elif node.name.startswith(("save", "write", "export")):
                    text = f"`{node.name}` writes results back out."
                else:
                    text = f"`{node.name}` groups related logic so callers can reuse it."
                callouts.append((node.lineno, text.replace("`", "")))
            elif isinstance(node, ast.ClassDef):
                callouts.append((node.lineno, f"`{node.name}` groups state and behavior behind one interface.".replace("`", "")))

    for pattern, text in [
        ("FastAPI", "FastAPI route setup: this exposes backend behavior over HTTP."),
        ("UploadFile", "Uploaded files enter the system here before processing."),
        ("OCR", "OCR/text extraction branch: scanned files need image-to-text handling."),
        ("json", "JSON handling keeps model output and test results machine-readable."),
        ("pandas", "Pandas is used here for tabular reporting and accuracy summaries."),
    ]:
        for i, line in enumerate(lines, 1):
            if pattern in line:
                callouts.append((i, text))
                break

    return callouts


def summarize_text(relative_path, lines):
    ext = Path(relative_path).suffix.lower()
    joined = "\n".join(lines)
    callouts = []

    if ext == ".py":
        return summarize_python(ROOT / relative_path, lines)
    if ext in {".jsx", ".js"}:
        for i, line in enumerate(lines, 1):
            if "import " in line:
                callouts.append((i, "Imports bring React, API helpers, styling, or build tools into this module."))
                break
        for i, line in enumerate(lines, 1):
            if re.search(r"function |const .*=>|export default", line):
                callouts.append((i, "Component/function boundary: this is where the UI behavior is assembled."))
                break
        for i, line in enumerate(lines, 1):
            if "fetch" in line or "axios" in line or "API" in line:
                callouts.append((i, "Backend call: the frontend talks to the extraction API here."))
                break
        if "useState" in joined:
            callouts.append((next(i for i, l in enumerate(lines, 1) if "useState" in l), "React state tracks uploads, progress, errors, and displayed results."))
    elif ext == ".css":
        for i, line in enumerate(lines, 1):
            if line.strip().endswith("{"):
                callouts.append((i, "Selector block: these rules control the visual treatment for matching UI elements."))
        for i, line in enumerate(lines, 1):
            if "@media" in line:
                callouts.append((i, "Responsive rule: this adapts the layout for smaller screens."))
                break
    elif ext == ".html":
        for i, line in enumerate(lines, 1):
            if "<div id=\"root\"" in line:
                callouts.append((i, "React mount point: the app renders into this element."))
                break
        for i, line in enumerate(lines, 1):
            if "script" in line:
                callouts.append((i, "The module script boots the frontend bundle."))
                break
    elif ext == ".toml":
        for i, line in enumerate(lines, 1):
            if "dependencies" in line:
                callouts.append((i, "Dependency list: these packages define the backend runtime stack."))
                break
        for i, line in enumerate(lines, 1):
            if "scripts" in line or "project" in line:
                callouts.append((i, "Project metadata: tooling reads this to install and run the app."))
                break
    elif Path(relative_path).name == "package.json":
        for i, line in enumerate(lines, 1):
            if "\"scripts\"" in line:
                callouts.append((i, "NPM scripts: these commands run, build, and preview the frontend."))
                break
        for i, line in enumerate(lines, 1):
            if "\"dependencies\"" in line:
                callouts.append((i, "Frontend dependencies: React and related packages are declared here."))
                break
    else:
        callouts.append((1, "Project ignore rules keep generated/cache files out of version control."))

    return callouts


def split_visual_line(line):
    if len(line) <= MAX_CODE_CHARS:
        return [line]
    chunks = []
    while len(line) > MAX_CODE_CHARS:
        chunks.append(line[:MAX_CODE_CHARS])
        line = "    " + line[MAX_CODE_CHARS:]
    chunks.append(line)
    return chunks


def visual_lines(lines):
    rendered = []
    source_to_visual = {}
    for number, line in enumerate(lines, 1):
        chunks = split_visual_line(line.rstrip("\n").replace("\t", "    "))
        source_to_visual[number] = len(rendered)
        for index, chunk in enumerate(chunks):
            rendered.append((number if index == 0 else None, chunk))
    return rendered, source_to_visual


def draw_code_line(c, rel_path, text, x, y):
    try:
        lexer = get_lexer_for_filename(rel_path)
    except Exception:
        lexer = None
    c.setFont(FONT_NAME, CODE_FONT_SIZE)
    cursor = x
    tokens = lex(text, lexer) if lexer else [(Token.Text, text)]
    for token_type, value in tokens:
        value = html.unescape(value).replace("\n", "")
        if not value:
            continue
        c.setFillColor(color_for_token(token_type))
        c.drawString(cursor, y, value)
        cursor += stringWidth(value, FONT_NAME, CODE_FONT_SIZE)


def draw_callout(c, page_index, line_no, text, side, source_to_visual, start_visual):
    visual_index = source_to_visual.get(line_no)
    if visual_index is None:
        return
    relative_index = visual_index - start_visual
    if relative_index < 0 or relative_index >= LINES_PER_PAGE:
        return

    target_y = CODE_Y_TOP - CODE_PAD_Y - (relative_index * LINE_H) + 2
    is_left = side == "left"
    x = LEFT_X if is_left else RIGHT_X
    y = min(PAGE_H - MARGIN - TITLE_H - 10, max(MARGIN + 90, target_y + 34))
    c.setStrokeColor(colors.HexColor("#d8d8d8"))
    c.setFillColor(colors.HexColor("#ffffff"))
    c.roundRect(x - 10, y - 12, CALLOUT_W + 20, 78, 6, stroke=1, fill=1)
    c.setFillColor(colors.HexColor("#222222"))
    c.setFont(FONT_BOLD, 13)
    c.drawString(x, y + 42, f"Line {line_no}")
    draw_wrapped_text(c, text, x, y + 22, CALLOUT_W, size=13, leading=15, fill=colors.HexColor("#222222"))

    start_x = x + CALLOUT_W + 10 if is_left else x - 10
    end_x = CODE_X + LINE_NO_W + CODE_PAD_X if is_left else CODE_X + CODE_W - 12
    draw_arrow(c, start_x, y + 18, end_x, target_y + 4)


def render_pdf(relative_path):
    source_path = ROOT / relative_path
    lines = source_path.read_text(encoding="utf-8").splitlines()
    rendered_lines, source_to_visual = visual_lines(lines)
    callouts = summarize_text(relative_path, lines)
    output_path = DOCS_DIR / output_name(relative_path)

    c = canvas.Canvas(str(output_path), pagesize=(PAGE_W, PAGE_H), pageCompression=1)
    total_pages = max(1, (len(rendered_lines) + LINES_PER_PAGE - 1) // LINES_PER_PAGE)

    for page in range(total_pages):
        start = page * LINES_PER_PAGE
        page_lines = rendered_lines[start : start + LINES_PER_PAGE]
        c.setFillColor(colors.white)
        c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)

        c.setFillColor(colors.HexColor("#111111"))
        c.setFont(FONT_BOLD, 30)
        c.drawString(MARGIN, PAGE_H - MARGIN - 18, "Readable Code Explanation")
        c.setFont(FONT_TEXT, 16)
        c.setFillColor(colors.HexColor("#444444"))
        c.drawString(MARGIN, PAGE_H - MARGIN - 46, relative_path)

        c.setFillColor(colors.HexColor("#fbfbfb"))
        c.setStrokeColor(colors.HexColor("#cfcfcf"))
        c.rect(CODE_X, CODE_Y_TOP - CODE_H, CODE_W, CODE_H, stroke=1, fill=1)
        c.setFillColor(colors.HexColor("#f1f1f1"))
        c.rect(CODE_X, CODE_Y_TOP - CODE_H, LINE_NO_W, CODE_H, stroke=0, fill=1)

        y = CODE_Y_TOP - CODE_PAD_Y
        for number, code in page_lines:
            if number is not None:
                c.setFillColor(colors.HexColor("#777777"))
                c.setFont(FONT_NAME, CODE_FONT_SIZE)
                c.drawRightString(CODE_X + LINE_NO_W - 10, y, str(number))
            draw_code_line(c, relative_path, code, CODE_X + LINE_NO_W + CODE_PAD_X, y)
            y -= LINE_H

        visible_callouts = [
            item for item in callouts if item[0] in source_to_visual and start <= source_to_visual[item[0]] < start + LINES_PER_PAGE
        ][:8]
        for index, (line_no, text) in enumerate(visible_callouts):
            draw_callout(c, page, line_no, text, "left" if index % 2 == 0 else "right", source_to_visual, start)

        c.setFillColor(colors.HexColor("#555555"))
        c.setFont(FONT_TEXT, 13)
        c.drawRightString(PAGE_W - MARGIN, MARGIN / 2, f"Page {page + 1} of {total_pages}")
        c.showPage()

    c.save()


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    for pdf in DOCS_DIR.glob("*.pdf"):
        pdf.unlink()
    for relative_path in SOURCE_FILES:
        if (ROOT / relative_path).is_file():
            render_pdf(relative_path)


if __name__ == "__main__":
    main()
