"""PDF generation tool: convert markdown/HTML content to PDF files."""
import logging
import os
import re
import json
from pathlib import Path

logger = logging.getLogger(__name__)

WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent / "workspace"
PDF_OUTPUT_DIR = WORKSPACE_DIR / "pdfs"


def _md_to_html(md: str) -> str:
    """Minimal markdown → HTML conversion for PDF rendering.
    Handles headings, bold, italic, lists, tables, hr, and paragraphs."""
    lines = md.split("\n")
    html_lines: list[str] = []
    in_ul = False
    in_ol = False
    in_table = False
    table_header_done = False

    for line in lines:
        stripped = line.strip()

        # Close open lists if line isn't a list item
        if in_ul and not stripped.startswith(("- ", "* ", "+ ")):
            html_lines.append("</ul>")
            in_ul = False
        if in_ol and not re.match(r"^\d+\.\s", stripped):
            html_lines.append("</ol>")
            in_ol = False
        # Close table if line doesn't start with |
        if in_table and not stripped.startswith("|"):
            html_lines.append("</table>")
            in_table = False
            table_header_done = False

        # Horizontal rule
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            html_lines.append("<hr>")
            continue

        # Headings
        hm = re.match(r"^(#{1,6})\s+(.*)", stripped)
        if hm:
            level = len(hm.group(1))
            text = _inline_fmt(hm.group(2))
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        # Unordered list
        ulm = re.match(r"^[-*+]\s+(.*)", stripped)
        if ulm:
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{_inline_fmt(ulm.group(1))}</li>")
            continue

        # Ordered list
        olm = re.match(r"^\d+\.\s+(.*)", stripped)
        if olm:
            if not in_ol:
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{_inline_fmt(olm.group(1))}</li>")
            continue

        # Table row
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Skip separator row (|---|---|)
            if all(re.match(r"^:?-+:?$", c) for c in cells):
                continue
            if not in_table:
                html_lines.append('<table border="1" style="border-collapse: collapse; width: 100%;">')
                in_table = True
            tag = "th" if not table_header_done else "td"
            style = ' style="padding: 8px; background: #f5f5f5;"' if tag == "th" else ' style="padding: 8px;"'
            row = "".join(f"<{tag}{style}>{_inline_fmt(c)}</{tag}>" for c in cells)
            html_lines.append(f"<tr>{row}</tr>")
            if tag == "th":
                table_header_done = True
            continue

        # Empty line
        if not stripped:
            html_lines.append("")
            continue

        # Paragraph
        html_lines.append(f"<p>{_inline_fmt(stripped)}</p>")

    # Close any open tags
    if in_ul:
        html_lines.append("</ul>")
    if in_ol:
        html_lines.append("</ol>")
    if in_table:
        html_lines.append("</table>")

    return "\n".join(html_lines)


def _inline_fmt(text: str) -> str:
    """Apply inline markdown formatting: bold, italic, code, links."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"_(.+?)_", r"<em>\1</em>", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r'<code style="background: #f0f0f0; padding: 1px 4px; border-radius: 3px;">\1</code>', text)
    # Links
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', text)
    return text


_BASE_CSS = """
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #222;
}
h1 { font-size: 20pt; margin-bottom: 6pt; color: #111; }
h2 { font-size: 16pt; margin-top: 14pt; margin-bottom: 4pt; color: #222; }
h3 { font-size: 13pt; margin-top: 10pt; margin-bottom: 3pt; color: #333; }
h4, h5, h6 { font-size: 11pt; margin-top: 8pt; margin-bottom: 2pt; }
p { margin: 4pt 0; }
ul, ol { margin: 4pt 0; padding-left: 20pt; }
li { margin: 2pt 0; }
hr { border: none; border-top: 1px solid #ccc; margin: 10pt 0; }
table { margin: 6pt 0; }
th { font-weight: bold; text-align: left; }
code { font-family: Courier, monospace; font-size: 10pt; }
a { color: #0066cc; }
strong { font-weight: bold; }
em { font-style: italic; }
"""


def generate_pdf(content: str, filename: str = "document.pdf", title: str | None = None) -> str:
    """Generate a PDF from markdown/text content. Returns the output file path."""
    import fitz

    # Ensure output directory
    PDF_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    if not filename.endswith(".pdf"):
        filename += ".pdf"
    filename = re.sub(r'[^\w\s\-.]', '', filename).strip()
    if not filename or filename == ".pdf":
        filename = "document.pdf"

    out_path = PDF_OUTPUT_DIR / filename

    # If content looks like HTML already (has tags), use it directly; otherwise convert from markdown
    if re.search(r"<(h[1-6]|p|div|table|ul|ol)\b", content):
        body_html = content
    else:
        body_html = _md_to_html(content)

    # Wrap in full HTML with styling; skip title if content already starts with a heading
    has_heading = body_html.strip().startswith("<h1") or content.strip().startswith("# ")
    title_html = f"<h1>{title}</h1>" if title and not has_heading else ""
    full_html = f"""<!DOCTYPE html>
<html>
<head><style>{_BASE_CSS}</style></head>
<body>
{title_html}
{body_html}
</body>
</html>"""

    # Render to PDF using pymupdf Story API
    story = fitz.Story(full_html)
    writer = fitz.DocumentWriter(str(out_path))
    mediabox = fitz.paper_rect("letter")  # 8.5 x 11 inches
    content_rect = mediabox + (54, 54, -54, -54)  # 0.75 inch margins

    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(content_rect)
        story.draw(dev)
        writer.end_page()

    writer.close()

    size_kb = os.path.getsize(out_path) / 1024
    logger.info("Generated PDF: %s (%.1f KB)", out_path, size_kb)
    return str(out_path)


def parse_pdf_tool_args(raw: str) -> dict:
    """Parse generate_pdf tool call arguments."""
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # Fallback: try to find JSON in the string
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return {"content": raw}


def get_pdf_tool_openai_def() -> list[dict]:
    """OpenAI-compatible tool definition for generate_pdf."""
    return [
        {
            "type": "function",
            "function": {
                "name": "generate_pdf",
                "description": (
                    "Generate a PDF document from markdown or text content. "
                    "Use this when the user asks to create, generate, or export a PDF — "
                    "contracts, reports, invoices, letters, resumes, summaries, etc. "
                    "Write the full document content in markdown with headings, lists, "
                    "tables, bold/italic as needed. The tool renders it to a professional PDF."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": (
                                "The document content in markdown format. Use headings (# ## ###), "
                                "bold (**text**), italic (*text*), lists (- item), tables "
                                "(| col1 | col2 |), and horizontal rules (---) for formatting."
                            ),
                        },
                        "filename": {
                            "type": "string",
                            "description": "Output filename (e.g. 'contract.pdf', 'invoice.pdf'). Defaults to 'document.pdf'.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Optional title rendered at the top of the PDF. If omitted, use a # heading in content instead.",
                        },
                    },
                    "required": ["content"],
                },
            },
        }
    ]
