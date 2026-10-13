# Northstar CRM for WooCommerce

A local Flask + SQLite CRM built from the attached `crm.zip` starter and redesigned with a responsive dashboard. It imports WooCommerce orders and customer profiles, stores billing contact/address details, tracks sync activity, segments customers, and records email workflow activity.

## CRM features

- Dashboard revenue trend, average order value, repeat customer count, recent orders, and sync health.
- Search/filter orders by status, order number, customer name, or email.
- Customer search and VIP/Returning/New segments, with filtered CSV export.
- Customer order history and billing profile; email templates and delivery log on the customer page.
- Store activity log, REST connection check, manual sync, and signed webhook support.

## Start here

1. Install Python 3.10+ if needed. In PowerShell, from this folder run:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   Copy-Item .env.example .env
   ```

2. In WordPress, install/activate WooCommerce, add three test orders, then go to **WooCommerce → Settings → Advanced → REST API → Add key**. Choose **Read** permission for CRM data sync. A test order needs a billing name, email, phone, and address.
3. Edit `.env`; set `WOO_URL` to your store root URL and paste the consumer key/secret. Keep `.env` private; it is excluded from Git.
4. Start the CRM with `python app.py` and open `http://127.0.0.1:5000`. Click **Test WooCommerce connection**, then **Sync store**. Customer pages include billing address, phone, order history, spend, and email history.

## Email workflows and webhooks

Emails are recorded without being sent until SMTP settings are configured. Fill `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD` in `.env` to enable sending; test with your own address first. The customer page offers order confirmation, shipped, and win-back templates.

For near-real-time order updates, expose this local app through a trusted HTTPS host, set a long random `WOO_WEBHOOK_SECRET`, and configure a WooCommerce order-created/updated webhook pointing to `/webhook` with that same secret. The app rejects webhook deliveries until a secret is configured and verifies WooCommerce's signature. For a local-only demo, manual sync is simpler.

## Important

- This app binds to `127.0.0.1` and is intended for a private local demo. It is not an internet-facing, multi-user production CRM; add login/roles, HTTPS deployment, backups, and operational monitoring before hosting it publicly.
- API credentials and customer personal data are sensitive. Use a read-only WooCommerce key, never paste keys into chat, and keep `.env` and `crm.db` private.
- The real store and keys cannot be created from this folder. They must be provisioned in your WordPress account. No live connection was possible here because no store URL/API keys were supplied.
