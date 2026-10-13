import base64
import csv
import hashlib
import hmac
import io
import json
import os
import secrets

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for

load_dotenv()

import db  # noqa: E402
import mailer  # noqa: E402
import woo  # noqa: E402

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
db.init()

@app.before_request
def protect_posts():
    if request.method == "POST" and request.endpoint != "webhook":
        token = session_token()
        if not hmac.compare_digest(request.form.get("csrf_token", ""), token):
            abort(400, "Your form expired. Refresh and try again.")

def session_token():
    from flask import session
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]

SYMBOLS = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}


@app.template_filter("money")
def money(value, currency=None):
    currency = currency or db.latest_currency()
    return f"{SYMBOLS.get(currency, currency + ' ')}{float(value or 0):,.2f}"


@app.template_filter("day")
def day(value):
    return (value or "")[:10]


@app.template_filter("fromjson")
def fromjson(value):
    return json.loads(value or "[]")


@app.context_processor
def inject():
    return {"template_labels": mailer.LABELS, "csrf_token": session_token(),
            "store_connected": bool(os.getenv("WOO_URL") and os.getenv("WOO_KEY") and os.getenv("WOO_SECRET")),
            "email_ready": bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))}


def send_template(customer, order, key):
    subject, body = mailer.render(key, customer, order)
    status, note = mailer.send(customer["email"], subject, body)
    db.add_message(
        customer["id"], order["id"] if order else None, key, subject, status, note
    )
    return status


@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",
        stats=db.stats(),
        recent_orders=db.orders(limit=5),
        recent_messages=db.messages(limit=5),
        revenue_series=db.monthly_revenue(),
        last_sync=db.sync_log(limit=1),
    )


@app.route("/customers")
def customers_page():
    q = request.args.get("q", "").strip()
    segment = request.args.get("segment", "")
    customers = db.customers(q)
    if segment in ("VIP", "Returning", "New"):
        customers = [c for c in customers if c["segment"] == segment]
    return render_template("customers.html", customers=customers, q=q, selected_segment=segment)


@app.route("/customers/export")
def export_customers():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Phone", "Address", "City", "Region", "Postcode", "Country", "Segment", "Orders", "Total spent", "Last order"])
    rows = db.customers(request.args.get("q", "").strip())
    segment = request.args.get("segment", "")
    if segment in ("VIP", "Returning", "New"):
        rows = [c for c in rows if c["segment"] == segment]
    for c in rows:
        values = [
            f"{c['first_name'] or ''} {c['last_name'] or ''}".strip(), c["email"], c["phone"],
            ", ".join(x for x in (c["address_1"], c["address_2"]) if x), c["city"], c["state"],
            c["postcode"], c["country"], c["segment"], c["order_count"], f"{c['spent']:.2f}", c["last_order"],
        ]
        # Guard spreadsheet users from cells interpreted as formulas.
        writer.writerow(["'" + str(v) if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for v in values])
    response = app.response_class(output.getvalue(), content_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=northstar-customers.csv"
    return response


@app.route("/segments")
def segments_page():
    customers = db.customers()
    counts = {name: sum(c["segment"] == name for c in customers) for name in ("VIP", "Returning", "New")}
    return render_template("segments.html", counts=counts, total=len(customers))


@app.route("/workflows")
def workflows_page():
    return render_template("workflows.html", messages=db.messages(limit=8), stats=db.stats())


@app.route("/customers/<int:cid>")
def customer_page(cid):
    c = db.customer(cid)
    if not c:
        abort(404)
    return render_template(
        "customer.html",
        c=c,
        orders=db.orders(customer_id=cid),
        messages=db.messages(customer_id=cid),
    )


@app.post("/customers/<int:cid>/email")
def customer_email(cid):
    c = db.customer(cid)
    key = request.form.get("template")
    if not c or key not in mailer.TEMPLATES:
        abort(400)
    status = send_template(c, db.latest_order(cid), key)
    flash(f"Email '{mailer.LABELS[key]}': {status}", "ok" if status == "sent" else "info")
    return redirect(url_for("customer_page", cid=cid))


@app.route("/orders")
def orders_page():
    status = request.args.get("status", "")
    q = request.args.get("q", "").strip()
    return render_template(
        "orders.html",
        orders=db.orders(status=status or None, q=q, limit=200),
        statuses=db.order_statuses(),
        selected=status,
        q=q,
    )


@app.route("/logs")
def logs_page():
    return render_template("logs.html", logs=db.sync_log())


@app.post("/sync")
def sync():
    try:
        orders = woo.fetch_all("orders")
        woo_customers = woo.fetch_all("customers")
        for wc in woo_customers:
            billing = dict(wc.get("billing") or {})
            billing["email"] = wc.get("email") or billing.get("email")
            billing["first_name"] = wc.get("first_name") or billing.get("first_name")
            billing["last_name"] = wc.get("last_name") or billing.get("last_name")
            if billing.get("email"):
                db.upsert_customer(billing, wc.get("date_created"))
        new = 0
        for o in orders:
            is_new, _, _ = db.upsert_order(o)
            new += 1 if is_new else 0
        db.log("sync", f"Fetched {len(orders)} orders, {new} new", "success")
        flash(f"Sync complete: {len(orders)} orders and {len(woo_customers)} customer profiles fetched; {new} new orders.", "ok")
    except Exception as e:
        db.log("sync", str(e), "failed")
        flash(f"Sync failed: {e}", "error")
    return redirect(request.referrer or url_for("dashboard"))


@app.post("/test-connection")
def test_connection():
    try:
        total = woo.test_connection()
        db.log("connection test", f"Connected, {total} orders visible", "success")
        flash(f"Connected to WooCommerce. {total} orders visible.", "ok")
    except Exception as e:
        db.log("connection test", str(e), "failed")
        flash(f"Could not connect: {e}", "error")
    return redirect(url_for("dashboard"))


@app.post("/webhook")
def webhook():
    raw = request.get_data()
    secret = os.getenv("WOO_WEBHOOK_SECRET")
    if not secret:
        db.log("webhook", "Rejected: WOO_WEBHOOK_SECRET is not configured", "failed")
        return "webhook secret is not configured", 503
    if secret:
        expected = base64.b64encode(
            hmac.new(secret.encode(), raw, hashlib.sha256).digest()
        ).decode()
        if not hmac.compare_digest(request.headers.get("X-WC-Webhook-Signature", ""), expected):
            db.log("webhook", "Rejected: bad signature", "failed")
            return "bad signature", 401

    payload = request.get_json(silent=True)
    if not payload or "id" not in payload or "billing" not in payload:
        return "ok", 200  # WooCommerce sends a form-encoded ping when a webhook is created

    is_new, old_status, order_row = db.upsert_order(payload)
    if order_row is None:
        db.log("webhook", f"Order {payload['id']} skipped: no billing email", "failed")
        return "skipped", 200

    order = next((o for o in db.orders() if o["id"] == order_row), None)
    customer = db.customer(order["customer_id"])
    sent = ""
    if is_new and not db.message_exists(order_row, "order_confirmation"):
        sent = " + confirmation email " + send_template(customer, order, "order_confirmation")
    elif old_status != payload["status"] and payload["status"] == "completed":
        if not db.message_exists(order_row, "order_shipped"):
            sent = " + shipped email " + send_template(customer, order, "order_shipped")
    db.log(
        "webhook",
        f"Order #{payload['id']} {'created' if is_new else 'updated'} ({payload['status']}){sent}",
        "success",
    )
    return "ok", 200


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=int(os.getenv("PORT", "5000")))
