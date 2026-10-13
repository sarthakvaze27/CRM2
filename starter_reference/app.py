import base64
import hashlib
import hmac
import json
import os

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for

load_dotenv()

import db  # noqa: E402
import mailer  # noqa: E402
import woo  # noqa: E402

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
db.init()

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
    return {"template_labels": mailer.LABELS}


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
    )


@app.route("/customers")
def customers_page():
    q = request.args.get("q", "").strip()
    return render_template("customers.html", customers=db.customers(q), q=q)


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
    return render_template(
        "orders.html",
        orders=db.orders(status=status or None),
        statuses=db.order_statuses(),
        selected=status,
    )


@app.route("/logs")
def logs_page():
    return render_template("logs.html", logs=db.sync_log())


@app.post("/sync")
def sync():
    try:
        orders = woo.fetch_all("orders")
        new = 0
        for o in orders:
            is_new, _, _ = db.upsert_order(o)
            new += 1 if is_new else 0
        db.log("sync", f"Fetched {len(orders)} orders, {new} new", "success")
        flash(f"Sync complete: {len(orders)} orders fetched, {new} new.", "ok")
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
    app.run(debug=True, port=5000)
