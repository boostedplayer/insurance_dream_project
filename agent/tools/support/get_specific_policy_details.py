from langchain_core.tools import tool
from pinecone import Pinecone
from dotenv import load_dotenv
import os

load_dotenv()
_pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
_policy_index = _pc.Index("insurance-policy-rag")

CONFIDENCE_THRESHOLD = 0.60


@tool
def get_specific_policy_details(query: str) -> dict:
    """
    use when user asks about a specific policy by name or wants coverage/exclusion details.
    handles typos and partial names via semantic search.
    returns description, coverage, exclusions, and agent guidance.
    """
    from agent.graph import embedding_model  # late import to avoid circular dep

    query_embedding = embedding_model.embed_query(query)

    results = _policy_index.query(
        vector=query_embedding,
        top_k=3,
        include_metadata=True,
        namespace="insurance-policies"
    )

    matches = results.get("matches", [])

    if not matches:
        return {
            "status": "no_match_found",
            "message": "No matching policy found in the knowledge base."
        }

    best = matches[0]
    score = best["score"]
    meta = best["metadata"]

    if score < CONFIDENCE_THRESHOLD:
        return {
            "status": "ambiguous_match",
            "message": "Could not confidently identify the policy from the query.",
            "possible_matches": [
                {
                    "policy_name": m["metadata"].get("policy_name"),
                    "policy_type": m["metadata"].get("policy_type"),
                    "match_score": round(m["score"], 3),
                }
                for m in matches
            ],
            "agent_guidance": (
                "Ask the user to confirm which policy they mean from the possible_matches list. "
                "Do not answer coverage questions until the policy is confirmed."
            )
        }

    return {
        "status": "success",
        "match_score": round(score, 3),
        "matched_policy": {
            "policy_id":          meta.get("policy_id"),
            "policy_name":        meta.get("policy_name"),
            "policy_type":        meta.get("policy_type"),
            "risk_category":      meta.get("risk_category"),
            "policy_description": meta.get("policy_description"),
            "coverage_amount":    meta.get("coverage_amount"),
            "base_premium":       meta.get("base_premium"),
            "what_covers":       meta.get("what_covers"),
            "what_doesnt_cover": meta.get("what_does_not_cover"),
        },
        "agent_guidance": (
            "Answer using only the matched_policy fields. "
            "If the answer isn't in what_covers, what_doesnt_cover, policy_description, or additional_benefits, "
            "say the detail wasn't found — do not invent coverage information."
        )
    }
