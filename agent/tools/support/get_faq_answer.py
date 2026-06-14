from langchain_core.tools import tool
from pinecone import Pinecone
from dotenv import load_dotenv
import os

load_dotenv()
_pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
_faq_index = _pc.Index("faq-rag")

FAQ_CONFIDENCE_THRESHOLD = 0.55
FAQ_SUPPLEMENT_THRESHOLD = 0.50


@tool
def get_faq_answer(query: str) -> dict:
    """
    Use when the user asks a general insurance question that doesn't require their account data.
    Examples: 'how do I file a claim?', 'what is a grace period?', 'how is my premium calculated?',
              'what documents do I need for renewal?', 'what happens if I miss a payment?'

    Searches the FAQ knowledge base and returns the most relevant answer.
    Do NOT use this for user-specific policy details — use the other tools for that.
    """
    from agent.graph import embedding_model  # Circular import se bachne ke liye yahan import karo, module load pe nahi

    query_embedding = embedding_model.embed_query(query)

    results = _faq_index.query(
        vector=query_embedding,
        top_k=3,
        include_metadata=True,
        namespace="insurance-faq"
    )

    matches = results.get("matches", [])

    if not matches:
        return {
            "status": "no_answer_found",
            "message": "No relevant FAQ found for this query.",
            "agent_guidance": "Answer from general insurance knowledge and clarify it's general guidance."
        }

    best = matches[0]
    score = best["score"]

    if score < FAQ_CONFIDENCE_THRESHOLD:
        return {
            "status": "low_confidence",
            "match_score": round(score, 3),
            "message": "Could not find a highly confident FAQ match.",
            "agent_guidance": (
                "Answer from general insurance knowledge but tell the user this is general guidance "
                "and they should contact support for specifics."
            )
        }

    supplementary = [
        {
            "question": m["metadata"].get("question"),
            "answer":   m["metadata"].get("answer"),
        }
        for m in matches[1:]
        if m["score"] >= FAQ_SUPPLEMENT_THRESHOLD
    ]

    return {
        "status": "success",
        "match_score": round(score, 3),
        "primary_answer": {
            "category": best["metadata"].get("category"),
            "question": best["metadata"].get("question"),
            "answer":   best["metadata"].get("answer"),
        },
        "supplementary_answers": supplementary,
        "agent_guidance": (
            "Use primary_answer to respond. Supplement with supplementary_answers only if they add "
            "relevant context. Keep the response concise and in plain English."
        )
    }
