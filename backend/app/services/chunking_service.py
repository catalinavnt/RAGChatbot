import re


def split_text_into_chunks(
    pages: list[dict],
    chunk_size: int = 1200
) -> list[dict]:
    """
    Splits PDF text into chunks based on numbered sections when possible.

    This is better for policy/manual/documentation PDFs because it tries to keep
    each logical section together.
    """

    chunks = []
    chunk_index = 0

    for page in pages:
        page_number = page["page"]
        text = page["text"]

        if not text.strip():
            continue

        sections = split_page_into_sections(text)

        for section in sections:
            section = section.strip()

            if not section:
                continue

            if len(section) <= chunk_size:
                chunks.append({
                    "chunk_index": chunk_index,
                    "page": page_number,
                    "text": section
                })
                chunk_index += 1
            else:
                sub_chunks = split_long_section(section, chunk_size)

                for sub_chunk in sub_chunks:
                    chunks.append({
                        "chunk_index": chunk_index,
                        "page": page_number,
                        "text": sub_chunk
                    })
                    chunk_index += 1

    return chunks


def split_page_into_sections(text: str) -> list[str]:
    """
    Splits text by headings like:
    1. Company Vacation Policy
    2. Remote Work Policy
    3. Expense Reimbursement Policy
    """

    cleaned_text = normalize_text(text)

    pattern = r"(?=\n?\d+\.\s+[A-Z][^\n]+)"

    sections = re.split(pattern, cleaned_text)

    sections = [
        section.strip()
        for section in sections
        if section.strip()
    ]

    return sections


def split_long_section(section: str, chunk_size: int) -> list[str]:
    """
    If a section is too long, split it by paragraphs without cutting words.
    """

    paragraphs = [
        paragraph.strip()
        for paragraph in section.split("\n")
        if paragraph.strip()
    ]

    chunks = []
    current_chunk = ""

    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 1 <= chunk_size:
            current_chunk += paragraph + "\n"
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            current_chunk = paragraph + "\n"

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


def normalize_text(text: str) -> str:
    """
    Cleans repeated spaces and excessive empty lines.
    """

    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()