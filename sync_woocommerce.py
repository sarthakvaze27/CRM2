#!/usr/bin/env python3
"""Fetch WooCommerce customers and orders into data.json for the CRM demo."""
import json, os, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path

BASE = os.environ.get("WC_STORE_URL", "").strip().rstrip("/")
KEY = os.environ.get("WC_CONSUMER_KEY", "").strip()
SECRET = os.environ.get("WC_CONSUMER_SECRET", "").strip()
OUT = Path(__file__).with_name("data.json")

def fetch(resource):
    if not BASE or not KEY or not SECRET:
        raise RuntimeError("Set WC_STORE_URL, WC_CONSUMER_KEY, and WC_CONSUMER_SECRET first.")
    query = urllib.parse.urlencode({"consumer_key": KEY, "consumer_secret": SECRET, "per_page": 100, "orderby": "date", "order": "desc"})
    url = f"{BASE}/wp-json/wc/v3/{resource}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "NorthstarCRM/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def main():
    try:
        orders = fetch("orders")
        customers = fetch("customers")
        OUT.write_text(json.dumps({"synced_at": __import__("datetime").datetime.now().astimezone().isoformat(), "orders": orders, "customers": customers}, indent=2), encoding="utf-8")
        print(f"Synced {len(orders)} orders and {len(customers)} customers to {OUT}")
        if len(orders) < 3:
            print("Note: fewer than 3 orders were returned. Create three test orders in WooCommerce to complete the demo.")
    except (RuntimeError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        print(f"WooCommerce sync failed: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
