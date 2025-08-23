import os
import requests

# Remotive API
def fetch_remotive_jobs(query="", limit=50):
    url = "https://remotive.com/api/remote-jobs"
    params = {"search": query}
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json().get("jobs", [])
    # Trim to limit and normalize fields
    return [{
        "title": j["title"],
        "company": j["company_name"],
        "location": j["candidate_required_location"],
        "description": j["description"],
        "requirements": "",
        "external_url": j["url"],
        "source": "Remotive",
        "created_at": j.get("publication_date")
    } for j in data[:limit]]

# Adzuna API
def fetch_adzuna_jobs(query="", limit=50):
    app_id  = os.environ["ADZUNA_APP_ID"]
    app_key = os.environ["ADZUNA_APP_KEY"]
    country = os.environ.get("ADZUNA_COUNTRY", "us")
    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": limit,
        "what": query,
    }
    resp = requests.get(url, params=params, timeout=10)
    data = resp.json().get("results", [])
    return [{
        "title": j["title"],
        "company": j["company"]["display_name"],
        "location": j["location"]["display_name"],
        "description": j.get("description", ""),
        "requirements": "",
        "external_url": j["redirect_url"],
        "source": "Adzuna",
        "created_at": j.get("created"),
    } for j in data]
