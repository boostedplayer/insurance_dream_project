from pinecone import Pinecone,ServerlessSpec
from dotenv import load_dotenv
from agent.graph import embedding_model
import pandas as pd
import os

load_dotenv()
api_key = os.getenv("PINECONE_API_KEY")

index_name = "insurance_policy_rag"
vector_dimension = 384

pc = Pinecone(api_key=api_key)


existing_index = pc.list_indexes().names()

if index_name not in existing_index:

    pc.create_index(  #use to create index
        name=index_name,
        dimension=vector_dimension,
        metric='cosine',
        spec = ServerlessSpec(
            cloud = 'aws',
            region='us-east-1'
        )
    )

    print(f"created index : {index_name}")
else:
    print(f"index already exists : {index_name}")

index = pc.Index(index_name) #use to connect to index.
#returns index client object

vectors = []

df = pd.read_csv("insurance_policy_dataset.csv")
print(f"loaded {len(df)} policies")

for _, row in df.iterrows():

    text_to_embed = f"""
    policy id : {row['policy_id']}
    policy name : {row['policy_name']}
    policy type : {row['policy_type']}
    risk category : {row['risk_category']}
    description : {row['policy_description']}
    coverage : {row['what_covers']}
    exclusions : {row['what_doesnt_covers']}
    addition benefits : {row['additional_benefits']}
    """

    embedding = embedding_model.embed_query(
        text_to_embed
    )

    vectors.append({
        'id': str(row['policy_id']),
        'values': embedding,
        'metadata': {
            "policy_id": int(row["policy_id"]),

            "policy_name": row["policy_name"],

            "policy_type": row["policy_type"],

            "risk_category": row["risk_category"],

            "policy_description": row["policy_description"],

            "coverage_amount": float(row["coverage_amount"]),

            "base_premium": float(row["base_premium"]),

            "what_covers": row["what_covers"],

            "what_does_not_cover": row["what_doesnt_covers"],

            "additional_benefits": row["additional_benefits"],
            "full_text" : text_to_embed
        }
    })

batch_size = 50

for i in range(0,len(vectors),batch_size):

    batch = vectors[i:i+batch_size]
    
    index.upsert(vectors=batch,namespace="insurance-policies")

    print(f"uploaded batch {i // batch_size + 1}")

print("all vectors uploaded successfully")
