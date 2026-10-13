import os

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("WOO_URL", "").rstrip("/") + "/wp-json/wc/v3"
AUTH = (os.getenv("WOO_KEY", ""), os.getenv("WOO_SECRET", ""))


def fetch_all(endpoint):
    """Fetch every page of a WooCommerce REST API list endpoint."""
    page, results = 1, []
    while True:
        r = requests.get(
            f"{BASE}/{endpoint}",
            auth=AUTH,
            params={"per_page": 100, "page": page},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        results += data
        if len(data) < 100:
            return results
        page += 1


def test_connection():
    """Returns the number of orders visible to the API keys (raises on failure)."""
    r = requests.get(
        f"{BASE}/orders", auth=AUTH, params={"per_page": 1}, timeout=20
    )
    r.raise_for_status()
    return int(r.headers.get("X-WP-Total", len(r.json())))
