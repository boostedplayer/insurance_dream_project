from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
from agent.graph import embedding_model

import pandas as pd
import os

load_dotenv()
api_key = os.getenv("PINECONE_API_KEY")

#create index and dimensions

index_name = "faq_rag"
vector_dimension = 384

pc = Pinecone(api_key = api_key)


existing_index = pc.list_indexes().names()


if index_name not in existing_index:

    pc.create_index(
        name = index_name,
        dimension=vector_dimension,
        metric = 'cosine',
        spec = ServerlessSpec(
            cloud = 'aws', 
            region = 'us-east-1'
        )
    )

    print(f"created index : {index_name}")

else:
    print(f"index already exists : {index_name}")


index = pc.Index(index_name) # to connect with index.


df = pd.read_csv("insurance_faq_dataset.csv")
print(f"loaded {len(df)} : faq")

vectors = []

for _,i in df.iterrows():

    text_to_embed = f"""
    faq id : {i['faq_id']}
    category : {i['category']}
    question : {i['question']}
    answer : {i['answer']}
    """

    embedding = embedding_model.embed_query(text_to_embed)

    vectors.append({
        "id": str(i["faq_id"]),
        "values": embedding,
        "metadata": {
            "faq_id": str(i["faq_id"]),
            "category": str(i["category"]),
            "question": str(i["question"]),
            "answer": str(i["answer"]),
            "full_text": text_to_embed
        }
    })

batch_size = 50

for i in range(0,len(vectors),batch_size):

    batch = vectors[i:i+batch_size]
    index.upsert(vectors=batch,namespace="insurance-faq")
    print(f"uploaded batch {i // batch_size + 1}")
print("all vectors uploaded successfully")