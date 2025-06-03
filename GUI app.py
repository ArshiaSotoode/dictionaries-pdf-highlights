import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import pymupdf
import requests
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from concurrent.futures import ThreadPoolExecutor, as_completed

# Set appearance mode and theme
ctk.set_appearance_mode("dark")  # "dark" or "light"
ctk.set_default_color_theme("blue")  # default, blue, dark-blue, green


class PDFDictionaryApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PDF Highlight Dictionary Extractor")
        self.geometry("720x520")
        self.minsize(700, 500)

        # Fonts & Styles
        header_font = ctk.CTkFont(size=20, weight="bold")

        # Header label
        self.header_label = ctk.CTkLabel(
            self, text="PDF Highlight Dictionary Extractor", font=header_font
        )
        self.header_label.pack(pady=(20, 10))

        # Frame for input controls
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=20, pady=(0, 15))

        # PDF Path Entry + Browse Button
        self.pdf_path_var = ctk.StringVar()
        self.pdf_entry = ctk.CTkEntry(
            input_frame,
            textvariable=self.pdf_path_var,
            placeholder_text="Select your PDF file...",
        )
        self.pdf_entry.pack(side="left", fill="x", expand=True, pady=10, padx=(0, 10))

        self.browse_button = ctk.CTkButton(
            input_frame, text="Browse", width=100, command=self.browse_file
        )
        self.browse_button.pack(side="left", pady=10)

        # Output filename
        output_frame = ctk.CTkFrame(self)
        output_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.output_name_var = ctk.StringVar(value="dict_table.pdf")
        self.output_label = ctk.CTkLabel(output_frame, text="Output PDF Name:")
        self.output_label.pack(side="left", padx=(0, 10))

        self.output_entry = ctk.CTkEntry(
            output_frame, textvariable=self.output_name_var
        )
        self.output_entry.pack(side="left", fill="x", expand=True)

        # Start Processing Button
        self.process_button = ctk.CTkButton(
            self, text="Start Processing", command=self.start_processing
        )
        self.process_button.pack(pady=20, ipadx=10, ipady=6)

        # Status / Log Textbox with Scrollbar
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self.status_text = ctk.CTkTextbox(
            log_frame, wrap="word", state="disabled", height=14
        )
        self.status_text.pack(side="left", fill="both", expand=True, pady=5)

        scrollbar = ctk.CTkScrollbar(log_frame, command=self.status_text.yview)
        scrollbar.pack(side="right", fill="y", pady=5)

        self.status_text.configure(yscrollcommand=scrollbar.set)

    def browse_file(self):
        filetypes = [("PDF files", "*.pdf"), ("All files", "*.*")]
        filename = filedialog.askopenfilename(
            title="Select PDF file", filetypes=filetypes
        )
        if filename:
            self.pdf_path_var.set(filename)

    def log(self, message):
        self.status_text.configure(state="normal")
        self.status_text.insert("end", message + "\n")
        self.status_text.see("end")
        self.status_text.configure(state="disabled")

    def start_processing(self):
        pdf_path = self.pdf_path_var.get().strip()
        if not pdf_path:
            messagebox.showerror("Error", "Please select a PDF file first.")
            return

        output_file = self.output_name_var.get().strip()
        if not output_file.lower().endswith(".pdf"):
            output_file += ".pdf"

        self.process_button.configure(state="disabled")
        self.status_text.configure(state="normal")
        self.status_text.delete("1.0", "end")
        self.status_text.configure(state="disabled")

        threading.Thread(
            target=self.process_pdf, args=(pdf_path, output_file), daemon=True
        ).start()

    def process_pdf(self, pdf_path, output_file):
        try:
            self.log(f"Opening PDF: {pdf_path}")
            doc = pymupdf.open(pdf_path)
        except Exception as e:
            self.log(f"Error opening PDF: {e}")
            self.process_button.configure(state="normal")
            return

        highlighted_words = {}

        for page_num, page in enumerate(doc, start=1):
            self.log(f"Processing page {page_num}...")
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
                self.log(
                    f"Found highlighted words on page {page_num}: {set(highlights)}"
                )

        if not highlighted_words:
            self.log("No highlighted words found.")
            self.process_button.configure(state="normal")
            return

        self.log("Fetching definitions for highlighted words...")

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

        all_words = set(word for words in highlighted_words.values() for word in words)
        definitions = {}

        with ThreadPoolExecutor(max_workers=500) as executor:
            futures = {
                executor.submit(get_definition, word): word for word in all_words
            }
            for i, future in enumerate(as_completed(futures)):
                word, meaning = future.result()
                definitions[word] = meaning
                self.log(f"Fetched definition for '{word}' ({i+1}/{len(all_words)})")

        self.log("Generating output PDF...")

        data = [["Page number", "Definitions"]]
        small_style = ParagraphStyle(
            name="small", fontSize=8, alignment=TA_LEFT, leading=12
        )

        for page_num, words in highlighted_words.items():
            defs = []
            for word in sorted(set(words)):
                meaning = definitions.get(word, "Definition not found.")
                defs.append(f"<b>{word}</b>: {meaning}")
            full_text = "<br/><br/>".join(defs)
            data.append([str(page_num), Paragraph(full_text, small_style)])

        col_widths = [80, 400]

        pdf_doc = SimpleDocTemplate(
            output_file,
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
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (1, 1), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ]
        )
        table.setStyle(style)

        pdf_doc.build([table])

        self.log(f"PDF successfully generated: {output_file}")
        messagebox.showinfo("Success", f"Output PDF generated:\n{output_file}")
        self.process_button.configure(state="normal")


if __name__ == "__main__":
    app = PDFDictionaryApp()
    app.mainloop()
