"""Generate PDF from the DynaBooks Development Document."""

import os
import markdown
from xhtml2pdf import pisa

DOC_DIR = os.path.dirname(os.path.abspath(__file__))
MD_FILE = os.path.join(DOC_DIR, "DynaBooks_Development_Document.md")
PDF_FILE = os.path.join(DOC_DIR, "DynaBooks_Development_Document.pdf")

CSS = """
@page {
    size: letter;
    margin: 2cm 2.5cm;
    @frame footer {
        -pdf-frame-content: footerContent;
        bottom: 0.5cm;
        margin-left: 2.5cm;
        margin-right: 2.5cm;
        height: 1cm;
    }
}
body {
    font-family: Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.5;
    color: #1a1a1a;
}
h1 {
    font-size: 22pt;
    color: #1B3A5C;
    border-bottom: 3px solid #2E75B6;
    padding-bottom: 8px;
    margin-top: 30px;
    margin-bottom: 15px;
    page-break-after: avoid;
}
h2 {
    font-size: 16pt;
    color: #1B3A5C;
    border-bottom: 1px solid #d0d0d0;
    padding-bottom: 4px;
    margin-top: 25px;
    margin-bottom: 10px;
    page-break-after: avoid;
}
h3 {
    font-size: 12pt;
    color: #2E75B6;
    margin-top: 18px;
    margin-bottom: 8px;
    page-break-after: avoid;
}
h4 {
    font-size: 10pt;
    color: #333;
    font-weight: bold;
    margin-top: 12px;
    margin-bottom: 6px;
}
p {
    margin-bottom: 8px;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 12px;
    font-size: 9pt;
}
th {
    background-color: #1B3A5C;
    color: white;
    padding: 6px 8px;
    text-align: left;
    font-weight: bold;
}
td {
    padding: 5px 8px;
    border-bottom: 1px solid #e0e0e0;
    vertical-align: top;
}
tr:nth-child(even) td {
    background-color: #f8f9fa;
}
code {
    font-family: Courier, monospace;
    font-size: 8.5pt;
    background-color: #f0f0f0;
    padding: 1px 4px;
}
pre {
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4px;
    padding: 10px;
    font-size: 8pt;
    font-family: Courier, monospace;
    overflow: hidden;
    margin-bottom: 12px;
    white-space: pre-wrap;
    word-wrap: break-word;
}
ul, ol {
    margin-bottom: 8px;
    padding-left: 20px;
}
li {
    margin-bottom: 3px;
}
strong {
    color: #1B3A5C;
}
hr {
    border: none;
    border-top: 2px solid #2E75B6;
    margin: 20px 0;
}
"""


def generate_pdf():
    with open(MD_FILE, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    # Wrap tree diagrams in <pre> tags (lines starting with +-- or |)
    import re
    lines = html_body.split("\n")
    in_tree = False
    result = []
    tree_buf = []
    for line in lines:
        stripped = line.strip()
        # Detect tree lines (contain +-- or |   or start with common tree chars)
        is_tree = bool(re.match(r"^(\+--|[\|]\s{2,})", stripped))
        if is_tree and not in_tree:
            in_tree = True
            tree_buf = [stripped]
        elif is_tree and in_tree:
            tree_buf.append(stripped)
        elif in_tree and not is_tree:
            in_tree = False
            result.append("<pre>" + "\n".join(tree_buf) + "</pre>")
            tree_buf = []
            result.append(line)
        else:
            result.append(line)
    if tree_buf:
        result.append("<pre>" + "\n".join(tree_buf) + "</pre>")
    html_body = "\n".join(result)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{CSS}</style>
</head>
<body>
{html_body}
<div id="footerContent" style="text-align: center; font-size: 8pt; color: #888;">
    DynaBooks Development Document — DynaNav Systems Inc. — February 2026
</div>
</body>
</html>"""

    with open(PDF_FILE, "wb") as pdf_out:
        status = pisa.CreatePDF(html, dest=pdf_out)

    if status.err:
        print(f"Error generating PDF: {status.err}")
    else:
        print(f"PDF generated: {PDF_FILE}")


if __name__ == "__main__":
    generate_pdf()
