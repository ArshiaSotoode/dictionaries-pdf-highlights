import pymupdf

# Prompt user and clean the input
raw_input = input("Please enter the path of pdf: ").strip()
pdf_path = raw_input.strip("'\"")  # Remove surrounding quotes if present

doc = pymupdf.open(pdf_path)

highlighted_words = {}

for page_num, page in enumerate(doc, start=1):
    words = page.get_text(
        "words"
    )  # list of (x0, y0, x1, y1, "text", block_no, line_no, word_no)
    highlights = []

    for annot in page.annots():
        if annot.type[0] != 8:  # 8 = highlight
            continue

        quadpoints = (
            annot.vertices
        )  # a flat list of points: [x0, y0, x1, y1, ..., x7, y7]
        for i in range(0, len(quadpoints), 4):
            # Each highlight quad has 4 points: p0, p1, p2, p3
            quad = quadpoints[i : i + 4]
            if len(quad) < 4:
                continue
            rect = pymupdf.Quad(
                quad
            ).rect  # use Quad to calculate the bounding rectangle

            for w in words:
                word_rect = pymupdf.Rect(w[:4])
                if rect.intersects(word_rect):
                    # strips all of the punctuation and unwanted characters
                    stripped_highlighted_word = "".join(c for c in w[4] if c.isalnum())
                    highlights.append(stripped_highlighted_word)

    if highlights:
        highlighted_words[page_num] = highlights
