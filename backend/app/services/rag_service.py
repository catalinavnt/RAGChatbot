import os
import re
from typing import Any

import requests
from openai import OpenAI


USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "true").lower() == "true"

api_key = os.getenv("OPENAI_API_KEY")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://host.docker.internal:11434"
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")

client = None

if not USE_MOCK_LLM and LLM_PROVIDER == "openai" and api_key:
    client = OpenAI(
        api_key=api_key,
        timeout=60.0,
        max_retries=2
    )


def build_context_from_results(results: Any) -> tuple[str, list[dict]]:
    """
    Converts Chroma search results into:
    - context text for the AI model
    - sources list for the final API response
    """

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    context_parts = []
    sources = []

    for index, document_text in enumerate(documents):
        metadata = metadatas[index] if index < len(metadatas) else {}

        filename = metadata.get("filename", "unknown")
        page = metadata.get("page", "unknown")
        chunk_index = metadata.get("chunk_index", "unknown")

        context_parts.append(
            f"[Source {index + 1}: {filename}, page {page}]\n{document_text}"
        )

        sources.append({
            "source_number": index + 1,
            "filename": filename,
            "page": page,
            "chunk_index": chunk_index,
            "distance": distances[index] if index < len(distances) else None,
            "preview": document_text[:700],
            "text": document_text
        })

    context = "\n\n---\n\n".join(context_parts)

    return context, sources


def generate_mock_answer(question: str, sources: list[dict]) -> str:
    """
    Generates a simple demo answer without calling OpenAI.

    It tries to find relevant sentences from the retrieved source previews.
    This is not a real LLM answer, but it is useful for development/demo mode.
    """

    if not sources:
        return "I could not find relevant information in the uploaded documents."

    question_keywords = extract_keywords(question)

    best_sentences = []

    for source in sources:
        source_text = source.get("text", source.get("preview", ""))
        sentences = split_into_sentences(source_text)

        for sentence in sentences:
            sentence_lower = sentence.lower()

            if any(keyword in sentence_lower for keyword in question_keywords):
                best_sentences.append({
                    "sentence": sentence,
                    "source_number": source["source_number"]
                })

    if not best_sentences:
        first_source = sources[0]
        return (
            f"Based on the retrieved document section, the relevant information starts with: "
            f"{first_source['preview']}... "
            f"[Source {first_source['source_number']}]"
        )

    selected = best_sentences[:2]

    answer_parts = [
        f"{item['sentence']} [Source {item['source_number']}]"
        for item in selected
    ]

    return " ".join(answer_parts)

def extract_keywords(question: str) -> list[str]:
    stop_words = {
        "what", "how", "many", "much", "does", "do", "can", "the",
        "a", "an", "is", "are", "to", "of", "in", "on", "for",
        "with", "and", "or", "per", "week", "employees", "employee",
        "work", "working", "from", "when", "where", "who", "why",
        "which", "should", "would", "could"
    }

    normalized_question = question.lower()

    words = re.findall(r"\b[a-zA-Z][a-zA-Z\-]{2,}\b", normalized_question)

    keywords = [
        word
        for word in words
        if word not in stop_words
    ]

    return keywords


def split_into_sentences(text: str) -> list[str]:
    """
    Splits text into rough sentences.
    """

    normalized_text = " ".join(text.split())

    sentences = re.split(r"(?<=[.!?])\s+", normalized_text)

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]

def build_prompt(question: str, context: str) -> str:
    return f"""
You are an AI assistant that answers questions using only the provided PDF context.

Rules:
- Answer only based on the context.
- If the answer is not present in the context, say: "The information was not found in the uploaded documents."
- Be concise and clear.
- Mention the source numbers used, for example: [Source 1], [Source 2].
- Do not invent information.

Context:
{context}

Question:
{question}
"""

def generate_openai_answer(question: str, context: str, sources: list[dict]) -> dict:
    """
    Generates a real answer using OpenAI.
    """

    if client is None:
        return {
            "answer": "OpenAI client is not configured. Check OPENAI_API_KEY or enable USE_MOCK_LLM=true.",
            "sources": sources
        }

    prompt = build_prompt(question, context)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful RAG assistant for PDF documents."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2
    )

    answer = response.choices[0].message.content

    return {
        "answer": answer,
        "sources": sources, 
        "has_answer": "The information was not found in the uploaded documents." not in answer.lower()
    }


def generate_ollama_answer(question: str, context: str, sources: list[dict]) -> dict:
    prompt = build_prompt(question, context)

    response = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2
            }
        },
        timeout=120
    )

    response.raise_for_status()

    data = response.json()
    answer = data.get("response", "").strip()

    if not answer:
        answer = "The information was not found in the uploaded documents."

    return {
        "answer": answer,
        "sources": sources, 
        "has_answer": "The information was not found in the uploaded documents." not in answer.lower()
    }


def generate_answer(question: str, search_results: Any) -> dict:
    context, sources = build_context_from_results(search_results)

    if not context.strip():
        return {
            "answer": "I could not find relevant information in the uploaded documents.",
            "sources": [],
            "has_answer": False
        }

    if USE_MOCK_LLM or LLM_PROVIDER == "mock":
        answer = generate_mock_answer(question, sources)

        return {
            "answer": answer,
            "sources": sources,
            "has_answer": "The information was not found in the uploaded documents." not in answer.lower()
        }

    if LLM_PROVIDER == "ollama":
        return generate_ollama_answer(question, context, sources)

    if LLM_PROVIDER == "openai":
        return generate_openai_answer(question, context, sources)

    return {
        "answer": f"Unknown LLM provider: {LLM_PROVIDER}",
        "sources": sources,
        "has_answer": False
    }