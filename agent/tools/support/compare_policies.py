from langchain_core.tools import tool
from pinecone import Pinecone
from dotenv import load_dotenv
import os

load_dotenv()
_pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
_policy_index = _pc.Index("insurance-policy-rag")

COMPARE_THRESHOLD = 0.50


def _fetch_policy(query: str, embedding_model) -> dict | None:
    """fetch best-matching policy from pinecone for the given query."""
    vec = embedding_model.embed_query(query)
    result = _policy_index.query(
        vector=vec,
        top_k=1,
        include_metadata=True,
        namespace="insurance-policies"
    )
    matches = result.get("matches", [])
    if not matches or matches[0]["score"] < COMPARE_THRESHOLD:
        return None
    meta = matches[0]["metadata"]
    return {
        "policy_name":        meta.get("policy_name"),
        "policy_type":        meta.get("policy_type"),
        "risk_category":      meta.get("risk_category"),
        "policy_description": meta.get("policy_description"),
        "coverage_amount":    meta.get("coverage_amount"),
        "base_premium":       meta.get("base_premium"),
        "what_covers":       meta.get("what_covers"),
        "what_doesnt_cover": meta.get("what_does_not_cover"),
        "match_score":        round(matches[0]["score"], 3),
    }


@tool
def compare_policies(policy_a: str, policy_b: str) -> dict:
    """
    use when user wants to compare two policies side by side.
    policy_a and policy_b are the policy names/descriptions the user mentioned.
    returns a structured comparison of both.
    """
    from agent.graph import embedding_model

    result_a = _fetch_policy(policy_a, embedding_model)
    result_b = _fetch_policy(policy_b, embedding_model)

    if result_a is None and result_b is None:
        return {
            "status": "no_match",
            "message": "Could not find either policy in the knowledge base.",
            "agent_guidance": "Ask the user to clarify the policy names and try again."
        }

    if result_a is None:
        return {
            "status": "partial_match",
            "found": "policy_b",
            "policy_b": result_b,
            "agent_guidance": f"Could not find '{policy_a}'. Ask the user to clarify that name."
        }

    if result_b is None:
        return {
            "status": "partial_match",
            "found": "policy_a",
            "policy_a": result_a,
            "agent_guidance": f"Could not find '{policy_b}'. Ask the user to clarify that name."
        }

    return {
        "status": "success",
        "policy_a": result_a,
        "policy_b": result_b,
        "agent_guidance": (
            "Present a clear side-by-side comparison. Highlight key differences in: "
            "coverage amount, base premium, what is covered, what is excluded, and additional benefits. "
            "End with a neutral summary — do not recommend one over the other unless the user asks. "
            "If the user asks which is better for them, factor in their context from the conversation."
        )
    }
