"""FastAPI ki routes aur connection test karo — yeh batayega exactly kya problem hai."""
import requests

BASE = "http://localhost:8002"

print("=" * 55)
print("FastAPI connection test")
print("=" * 55)

# Health check
try:
    r = requests.get(f"{BASE}/", timeout=5)
    print(f"\n  GET /                 →  {r.status_code}  {r.json()}")
except requests.exceptions.ConnectionError:
    print(f"\n  GET /                 →  CONNECTION REFUSED (FastAPI nahi chal raha!)")
    print("  Pehle 'python run.py' chalao dusre terminal mein.\n")
    exit(1)
except Exception as e:
    print(f"\n  GET /                 →  ERROR: {e}\n")
    exit(1)

# Login
try:
    r = requests.post(f"{BASE}/api/auth/login",
                      json={"email": "test@insurance.com", "password": "password123"},
                      timeout=5)
    print(f"  POST /api/auth/login  →  {r.status_code}  {r.text[:300]}")
except Exception as e:
    print(f"  POST /api/auth/login  →  ERROR: {e}")

# Docs routes list
try:
    r = requests.get(f"{BASE}/openapi.json", timeout=5)
    paths = list(r.json().get("paths", {}).keys())
    print(f"\n  Registered routes ({len(paths)} total):")
    for p in sorted(paths):
        print(f"    {p}")
except Exception as e:
    print(f"  OpenAPI routes  →  ERROR: {e}")

print("=" * 55)
