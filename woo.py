import os
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

load_dotenv()

BASE = os.getenv("WOO_URL", "").rstrip("/") + "/wp-json/wc/v3"
AUTH = (os.getenv("WOO_KEY", ""), os.getenv("WOO_SECRET", ""))


def validate_config():
    host = urlparse(BASE.removesuffix("/wp-json/wc/v3")).hostname or ""
    if not host or host == "your-site.tastewp.com" or not AUTH[0] or not AUTH[1] or "xxxx" in (AUTH[0] + AUTH[1]).lower():
        raise RuntimeError("WooCommerce is not configured yet. Put your real store root URL, consumer key, and consumer secret in CRM\\.env (not .env.example), then restart the CRM.")


def fetch_all(endpoint):
    """Fetch every page of a WooCommerce REST API list endpoint."""
    validate_config()
    page, results = 1, []
    while True:
        r = requests.get(
            f"{BASE}/{endpoint}",
            auth=AUTH,
            params={"per_page": 100, "page": page},
            timeout=20,
        )
        r.raise_for_status()
        try:
            data = r.json()
        except ValueError as exc:
            raise RuntimeError(f"WooCommerce returned a non-JSON response (HTTP {r.status_code}). Check that WOO_URL in .env is the store root, for example https://shop.example.com, without /wp-admin or /wp-json/wc/v3.") from exc
        if isinstance(data, dict):
            raise RuntimeError(data.get("message") or "WooCommerce returned an unexpected response. Check the store URL and REST API key permissions.")
        if not isinstance(data, list):
            raise RuntimeError("WooCommerce returned an unexpected response format. Check WOO_URL in .env.")
        results += data
        if len(data) < 100:
            return results
        page += 1


def test_connection():
    """Returns the number of orders visible to the API keys (raises on failure)."""
    validate_config()
    r = requests.get(
        f"{BASE}/orders", auth=AUTH, params={"per_page": 1}, timeout=20
    )
    r.raise_for_status()
    return int(r.headers.get("X-WP-Total", len(r.json())))
