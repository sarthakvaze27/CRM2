import json
import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

TEMPLATES = {
    "order_confirmation": (
        "We received your order #{order_id}",
        "Hi {name},\n\nThanks for shopping with us. We have received order #{order_id}:\n\n"
        "{items}\n\nTotal: {total}\n\nWe will let you know as soon as it ships.\n\n- {store}",
    ),
    "order_shipped": (
        "Your order #{order_id} is on its way",
        "Hi {name},\n\nGood news: order #{order_id} has been completed and is on its way.\n\n"
        "{items}\n\nThank you for your purchase.\n\n- {store}",
    ),
    "we_miss_you": (
        "We miss you, {name}",
        "Hi {name},\n\nIt has been a while since your last order. Use code WELCOME10 "
        "for 10% off your next purchase.\n\n- {store}",
    ),
}

LABELS = {
    "order_confirmation": "Order confirmation",
    "order_shipped": "Order shipped",
    "we_miss_you": "We miss you",
}


def render(key, customer, order):
    subject, body = TEMPLATES[key]
    items = ""
    order_id = ""
    total = ""
    if order is not None:
        order_id = order["woo_id"]
        total = f"{order['total']:.2f} {order['currency']}"
        items = "\n".join(
            f"- {i['name']} x {i['qty']}" for i in json.loads(order["items"] or "[]")
        )
    data = dict(
        name=customer["first_name"] or "there",
        order_id=order_id,
        items=items,
        total=total,
        store=os.getenv("SMTP_FROM_NAME", "Our store"),
    )
    return subject.format(**data), body.format(**data)


def send(to, subject, body):
    """Returns (status, note). Never raises, so a mail failure cannot break a sync."""
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    if not user or not password:
        return "not_sent", "SMTP not configured - message recorded only"
    msg = EmailMessage()
    msg["From"] = f"{os.getenv('SMTP_FROM_NAME', 'CRM')} <{user}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST", "smtp.gmail.com"),
                          int(os.getenv("SMTP_PORT", "587")), timeout=20) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        return "sent", ""
    except Exception as e:
        return "failed", str(e)
