import docx
from pathlib import Path


def parse_docx(file_path: str) -> str:
    """
    Extract raw text from a .docx file, including paragraphs and tables.
    Returns a single plain-text string ready for summarization.
    """
    document = docx.Document(file_path)
    full_text = []

   
    for block in _iter_block_items(document):
        if isinstance(block, docx.text.paragraph.Paragraph):
            if block.text.strip():
                full_text.append(block.text.strip())
        elif isinstance(block, docx.table.Table):
            full_text.append(_table_to_text(block))

    return "\n\n".join(full_text)


def _iter_block_items(document):
    """
    Yield paragraphs and tables in the order they appear in the document body.
    python-docx doesn't expose this directly -- we walk the underlying XML.
    """
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = document.element.body
    for child in body.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, document)
        elif isinstance(child, CT_Tbl):
            yield Table(child, document)


def _table_to_text(table) -> str:
    """
    Convert a docx table into a readable pipe-separated text block.
    LLMs parse this format well without needing real table structure.
    """
    rows_text = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        rows_text.append(" | ".join(cells))
    return "\n".join(rows_text)


def parse_pdf(file_path: str) -> str:
    """
    Extract raw text from a PDF file, page by page.
    """
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    full_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text and text.strip():
            full_text.append(text.strip())
    return "\n\n".join(full_text)


def parse_document(file_path: str) -> str:
    """
    Entry point: detects file type by extension and routes to the right parser.
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        return parse_docx(file_path)
    elif ext == ".pdf":
        return parse_pdf(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .docx or .pdf")