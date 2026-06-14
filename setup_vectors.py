"""
Ek baar ka setup — FAQ aur policy data ko embed karke Pinecone mein upload karo.

Yeh sirf EK BAAR chalao application shuru karne se pehle (ya jab bhi CSV data badal jaaye):
    python setup_vectors.py

Zaroorat hai:
  - PINECONE_API_KEY .env mein set ho
  - HUGGINGFACEHUB_ACCESS_TOKEN .env mein set ho
  - insurance_faq_dataset.csv project root mein present ho
  - insurance_policy_dataset.csv project root mein present ho
"""
import subprocess
import sys
import os

def run(label: str, module: str):
    print(f"\n{'='*50}")
    print(f"  {label}")
    print('='*50)
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )
    if result.returncode != 0:
        print(f"\n[ERROR] {label} failed. Check the output above.")
        sys.exit(1)
    print(f"[OK] {label} complete.")

if __name__ == "__main__":
    run("Setting up FAQ vectors (Pinecone index: faq_rag)", "agent.vector.faq_setup")
    run("Setting up Policy vectors (Pinecone index: insurance_policy_rag)", "agent.vector.policy_setup")
    print("\n✓ All Pinecone indexes are ready. You can now start the application.")
