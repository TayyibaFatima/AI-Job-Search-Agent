"""Check the Jooble key: python -m backend.dev_scripts.check_jooble"""
import os

import requests
from dotenv import load_dotenv

load_dotenv()

raw = os.getenv("JOOBLE_API_KEY")
if raw is None:
    raise SystemExit("JOOBLE_API_KEY was not found. Is .env in the project root?")

key = raw.strip().strip("\"'").strip()
print(f"Key found: {len(key)} characters, starts with {key[:4]!r}, ends with {key[-4:]!r}")
if raw != key:
    print("Note: the key had spaces or quotes around it (they are ignored now).")

response = requests.post(
    f"https://jooble.org/api/{key}",
    json={"keywords": "python developer", "location": "", "page": "1"},
    headers={
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (compatible; JobSearchAgent/1.0)",
    },
    timeout=20,
)
print("HTTP status:", response.status_code)
print("Reply:", response.text[:300])
if response.status_code == 200:
    print("Jobs returned:", len(response.json().get("jobs", [])))