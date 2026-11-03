from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException

from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware

from app.services.pdf_service import extract_text_from_pdf
from app.services.chunking_service import split_text_into_chunks
from app.services.vector_store_service import (
    add_chunks_to_vector_store, search_similar_chunks, count_chunks, reset_vector_store
)
from app.services.rag_service import generate_answer

app = FastAPI(
    title="AI PDF RAG Chatbot",
    description="Backend for uploading and chatting with PDF documents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class ChatRequest(BaseModel):
    question: str


def reindex_uploaded_documents() -> dict:
    pdf_files = list(UPLOAD_DIR.glob("*.pdf"))

    reset_vector_store()

    if not pdf_files:
        return {
            "indexed_files": 0,
            "indexed_chunks": 0
        }

    total_chunks = 0
    indexed_files = 0

    for pdf_file in pdf_files:
        pages = extract_text_from_pdf(str(pdf_file))
        chunks = split_text_into_chunks(pages)

        saved_chunks = add_chunks_to_vector_store(pdf_file.name, chunks)

        total_chunks += saved_chunks
        indexed_files += 1

    return {
        "indexed_files": indexed_files,
        "indexed_chunks": total_chunks
    }


@app.get("/")
def root():
    return {
        "message": "Backend is running inside Docker"
    }


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if file.filename is None:
        raise HTTPException(
            status_code=400,
            detail="File must have a filename"
        )

    filename = file.filename

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    file_path = UPLOAD_DIR / filename

    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    pages = extract_text_from_pdf(str(file_path))

    chunks = split_text_into_chunks(pages)

    saved_chunks = add_chunks_to_vector_store(filename, chunks)

    total_characters = sum(len(page["text"]) for page in pages)

    return {
        "filename": filename,
        "pages": len(pages),
        "chunks": len(chunks),
        "total_characters": total_characters,
        "message": "PDF uploaded and text extracted successfully"
    }

@app.get("/search")
def search_chunks(query: str):
    results = search_similar_chunks(query)

    return {
        "query": query,
        "results": results
    }

@app.post("/chat")
def chat_with_documents(request: ChatRequest):
    search_results = search_similar_chunks(
        query=request.question,
        n_results=3
    )

    rag_response = generate_answer(
        question=request.question,
        search_results=search_results
    )

    return {
        "question": request.question,
        "answer": rag_response["answer"],
        "sources": rag_response["sources"],
        "has_answer": rag_response["has_answer"]
    }

@app.get("/debug/chunks/count")
def get_chunks_count():
    return {
        "chunks_count": count_chunks()
    }

@app.post("/documents/reindex")
def reindex_documents():
    result = reindex_uploaded_documents()

    if result["indexed_files"] == 0:
        return {
            "message": "No PDF files found in uploads folder.",
            "indexed_files": 0,
            "indexed_chunks": 0
        }

    return {
        "message": "Documents reindexed successfully.",
        "indexed_files": result["indexed_files"],
        "indexed_chunks": result["indexed_chunks"]
    }

@app.get("/documents")
def list_documents():
    pdf_files = list(UPLOAD_DIR.glob("*.pdf"))

    documents = []

    for pdf_file in pdf_files:
        file_size_bytes = pdf_file.stat().st_size

        documents.append({
            "filename": pdf_file.name,
            "size_bytes": file_size_bytes,
            "size_kb": round(file_size_bytes / 1024, 2)
        })

    return {
        "documents": documents,
        "count": len(documents)
    }

@app.delete("/documents/{filename}")
def delete_document(filename: str):
    safe_filename = Path(filename).name
    file_path = UPLOAD_DIR / safe_filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    if file_path.suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files can be deleted"
        )

    file_path.unlink()

    reindex_result = reindex_uploaded_documents()

    return {
        "filename": safe_filename,
        "message": "Document deleted and vector store reindexed successfully.",
        "remaining_indexed_files": reindex_result["indexed_files"],
        "remaining_indexed_chunks": reindex_result["indexed_chunks"]
    }