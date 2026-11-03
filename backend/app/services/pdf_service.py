import fitz


def extract_text_from_pdf(file_path: str) -> list[dict]:
    """
    Extracts text from a PDF file page by page.

    Returns:
    [
        {"page": 1, "text": "..."},
        {"page": 2, "text": "..."}
    ]
    """

    pages = []

    document = fitz.open(file_path)

    for page_index in range(len(document)):
        page = document.load_page(page_index)
        text = page.get_text()

        pages.append({
            "page": page_index + 1,
            "text": text
        })

    document.close()

    return pages