from langchain_core.runnables import RunnableConfig
from agent.graph import embedding_model
from pinecone import Pinecone
from langchain_core.tools import tool
from dotenv import load_dotenv
import os


load_dotenv()
api_key = os.getenv("PINECONE_API_KEY")

pc = Pinecone(api_key=api_key)
policy_index = pc.Index("insurance_policy_rag")



def get_specific_policy_details(query: str, config : RunnableConfig):
    """
    Use when user asks about a specific policy by name.

    This tool uses semantic search, so it can handle:
    - typo in policy name
    - partial policy name
    - similar wording
    - natural language query about a policy

    Returns policy_id, policy_tenure, policy_description, coverage_amount,
    base_premium, what_covers, what_does_not_cover, and additional_benefits.
    
    """

    query_embedding = embedding_model.embed_query(query)

    results = policy_index.query(
        vector = query_embedding,
        top_k = 3,
        include_metadata=True,
        namespace = 'insurance-policies'
    )

    matches = results.get('matches',[])

    if not matches:
        return {
            "status": "no_match_found",
            "message": "No matching policy found."
        }
    
    best_match = matches[0]
    score = best_match['score']
    metadata = best_match['metadata']

    if score < 0.60:
        return {
            "status":"ambiguous_match",
            "message":"could not conifdently identify the policy",
            "possible_matches":[
                {
                    "policy_name":match['metadata'].get("policy_name"),
                    "policy_type":match['metadata'].get("policy_type"),
                    "match_score":round(match['score'],3),

                }
                for match in matches
            ],
            "agent_guidance": (
                "Ask the user to confirm which listed policy they are asking about. "
                "Do not answer policy-specific coverage questions until the policy is confirmed."
            )
        }
    return {
        "status": "success",
        "match_score": round(score, 3),
        "matched_policy": {
            "policy_id": metadata.get("policy_id"),
            "policy_name": metadata.get("policy_name"),
            "policy_type": metadata.get("policy_type"),
            "risk_category": metadata.get("risk_category"),
            "policy_description": metadata.get("policy_description"),
            "coverage_amount": metadata.get("coverage_amount"),
            "base_premium": metadata.get("base_premium"),
            "what_covers": metadata.get("what_covers"),
            "what_doesnt_covers": metadata.get("what_doesnt_covers"),
            "additional_benefits": metadata.get("additional_benefits"),
            "full_text": metadata.get("full_text")
        },
        "agent_guidance": (
            "Answer the user's question using only the matched policy details. "
            "If the answer is not explicitly present in what_covers, what_doesnt_covers, "
            "policy_description, or additional_benefits, say that the information was not found "
            "in the retrieved policy details. Do not invent coverage details."
        )
    }