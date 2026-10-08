import os
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"

params = {
    "app_id": APP_ID,
    "app_key": APP_KEY,
    "results_per_page": 10,
    "what": "AI machine learning",
    "where": "London",
    "content-type": "application/json"
}

response = requests.get(url, params=params)

print("Status:", response.status_code)

if response.status_code == 200:
    data = response.json()

    print("Jobs found:", len(data.get("results", [])))

    for job in data.get("results", []):
        print("\n--------------------")
        print("Title:", job.get("title"))
        print("Company:", job.get("company", {}).get("display_name"))
        print("Location:", job.get("location", {}).get("display_name"))
        print("URL:", job.get("redirect_url"))
else:
    print(response.text)