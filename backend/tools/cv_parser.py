try:
    import pymupdf
except ImportError:  # older PyMuPDF releases
    import fitz as pymupdf


def extract_cv_text(pdf_path):
    with pymupdf.open(pdf_path) as document:
        return "".join(page.get_text() for page in document)
