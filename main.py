import pymupdf
import requests
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from concurrent.futures import ThreadPoolExecutor, as_completed

# Prompt user and clean the input
raw_input = input("Please enter the path of pdf: ").strip()
pdf_path = raw_input.strip("'\"")

doc = pymupdf.open(pdf_path)

highlighted_words = {}

for page_num, page in enumerate(doc, start=1):
    words = page.get_text("words")
    highlights = []

    if page.annots():
        for annot in page.annots():
            if annot.type[0] != 8:
                continue

            quadpoints = annot.vertices
            for i in range(0, len(quadpoints), 4):
                quad = quadpoints[i : i + 4]
                if len(quad) < 4:
                    continue
                rect = pymupdf.Quad(quad).rect

                for w in words:
                    word_rect = pymupdf.Rect(w[:4])
                    if rect.intersects(word_rect):
                        stripped = "".join(c for c in w[4] if c.isalnum())
                        if stripped:
                            highlights.append(stripped)

    if highlights:
        highlighted_words[page_num] = highlights


def get_definition(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return word, data[0]["meanings"][0]["definitions"][0]["definition"]
    except:
        pass
    return word, "Definition not found."


# Use parallel requests to speed up
all_words = set(word for words in highlighted_words.values() for word in words)
definitions = {}

with ThreadPoolExecutor(max_workers=1000) as executor:
    futures = {executor.submit(get_definition, word): word for word in all_words}
    for future in as_completed(futures):
        word, meaning = future.result()
        definitions[word] = meaning

# Prepare table data
data = [["Page number", "Definitions"]]
small_style = ParagraphStyle(name="small", fontSize=8, alignment=TA_LEFT, leading=12)

for page_num, words in highlighted_words.items():
    defs = []
    for word in sorted(set(words)):
        meaning = definitions.get(word, "Definition not found.")
        defs.append(f"<b>{word}</b>: {meaning}")
    full_text = "<br/><br/>".join(defs)
    data.append([str(page_num), Paragraph(full_text, small_style)])

# PDF setup
col_widths = [80, 400]

pdf = SimpleDocTemplate(
    "dict_table.pdf",
    pagesize=A4,
    rightMargin=30,
    leftMargin=30,
    topMargin=30,
    bottomMargin=30,
)

table = Table(data, colWidths=col_widths, repeatRows=1)

style = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),  # Page numbers centered
        ("ALIGN", (1, 1), (-1, -1), "LEFT"),  # Definitions left aligned
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ]
)
table.setStyle(style)

pdf.build([table])
