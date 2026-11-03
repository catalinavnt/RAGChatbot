import os
from typing import Any

import chromadb


CHROMA_HOST = os.getenv("CHROMA_HOST", "chroma")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = "pdf_chunks"


client = chromadb.HttpClient(
    host=CHROMA_HOST,
    port=CHROMA_PORT
)


def get_collection():
    """
    Gets or creates the Chroma collection used for PDF chunks.
    """

    return client.get_or_create_collection(
        name=COLLECTION_NAME
    )


collection = get_collection()


def reset_vector_store() -> None:
    """
    Deletes and recreates the Chroma collection.
    Useful before a full reindex.
    """

    global collection

    try:
        client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass

    collection = get_collection()


def add_chunks_to_vector_store(filename: str, chunks: list[dict]) -> int:
    """
    Saves PDF chunks into Chroma.
    """

    if not chunks:
        return 0

    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        chunk_id = f"{filename}_chunk_{chunk['chunk_index']}"

        ids.append(chunk_id)
        documents.append(chunk["text"])
        metadatas.append({
            "filename": filename,
            "page": chunk["page"],
            "chunk_index": chunk["chunk_index"]
        })

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )

    return len(chunks)


def search_similar_chunks(query: str, n_results: int = 3) -> Any:
    """
    Searches the most relevant chunks for a query.
    """

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )

    return results


def count_chunks() -> int:
    """
    Returns how many chunks are currently stored in Chroma.
    """

    return collection.count()