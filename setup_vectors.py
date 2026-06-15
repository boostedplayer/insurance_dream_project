"""
one-time setup — embed FAQ + policy data and upload to Pinecone.

run once before starting the app (or whenever the CSVs change):
    python setup_vectors.py

needs:
  - PINECONE_API_KEY in .env
  - HUGGINGFACEHUB_ACCESS_TOKEN in .env
  - insurance_faq_dataset.csv at project root
  - insurance_policy_dataset.csv at project root
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
