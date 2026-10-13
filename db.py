import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crm.db")


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                first_name TEXT, last_name TEXT, phone TEXT,
                address_1 TEXT, address_2 TEXT,
                city TEXT, state TEXT, postcode TEXT, country TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                woo_id INTEGER UNIQUE NOT NULL,
                customer_id INTEGER,
                status TEXT, total REAL, currency TEXT,
                items TEXT,
                placed_at TEXT, updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER, order_id INTEGER,
                template TEXT, subject TEXT,
                status TEXT, note TEXT, sent_at TEXT
            );
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT, detail TEXT, status TEXT, time TEXT
            );
            """
        )
        columns = {r[1] for r in c.execute("PRAGMA table_info(customers)")}
        for name in ("address_1", "address_2", "postcode", "country"):
            if name not in columns:
                c.execute(f"ALTER TABLE customers ADD COLUMN {name} TEXT")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(event, detail, status):
    with conn() as c:
        c.execute(
            "INSERT INTO sync_log (event, detail, status, time) VALUES (?,?,?,?)",
            (event, detail, status, now()),
        )


def sync_log(limit=100):
    with conn() as c:
        return c.execute(
            "SELECT * FROM sync_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def upsert_customer(billing, created_at):
    email = (billing.get("email") or "").strip().lower()
    if not email:
        return None
    with conn() as c:
        row = c.execute("SELECT id FROM customers WHERE email=?", (email,)).fetchone()
        values = (
            billing.get("first_name"), billing.get("last_name"), billing.get("phone"),
            billing.get("address_1"), billing.get("address_2"), billing.get("city"),
            billing.get("state"), billing.get("postcode"), billing.get("country"),
        )
        if row:
            c.execute(
                "UPDATE customers SET first_name=?, last_name=?, phone=?, address_1=?, address_2=?, city=?, state=?, postcode=?, country=? WHERE id=?",
                values + (row["id"],),
            )
            return row["id"]
        cur = c.execute(
            "INSERT INTO customers (email, first_name, last_name, phone, address_1, address_2, city, state, postcode, country, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (email,) + values + (created_at,),
        )
        return cur.lastrowid


def upsert_order(o):
    """Save one WooCommerce order. Returns (is_new, old_status, order_row_id)."""
    customer_id = upsert_customer(o.get("billing", {}), o.get("date_created"))
    if customer_id is None:
        return False, None, None
    items = [
        {"name": i.get("name"), "qty": i.get("quantity"), "total": i.get("total")}
        for i in o.get("line_items", [])
    ]
    with conn() as c:
        row = c.execute(
            "SELECT id, status FROM orders WHERE woo_id=?", (o["id"],)
        ).fetchone()
        values = (
            customer_id, o.get("status"), float(o.get("total") or 0),
            o.get("currency"), json.dumps(items),
            o.get("date_created"), o.get("date_modified"),
        )
        if row:
            c.execute(
                "UPDATE orders SET customer_id=?, status=?, total=?, currency=?, items=?, "
                "placed_at=?, updated_at=? WHERE id=?",
                values + (row["id"],),
            )
            return False, row["status"], row["id"]
        cur = c.execute(
            "INSERT INTO orders (customer_id, status, total, currency, items, placed_at, updated_at, woo_id) "
            "VALUES (?,?,?,?,?,?,?,?)",
            values + (o["id"],),
        )
        return True, None, cur.lastrowid


def segment(spent, count):
    if spent >= 3000:
        return "VIP"
    if count <= 1:
        return "New"
    return "Returning"


def customers(q=""):
    like = f"%{q}%"
    with conn() as c:
        rows = c.execute(
            """
            SELECT c.*, COUNT(o.id) AS order_count,
                   COALESCE(SUM(o.total), 0) AS spent, MAX(o.placed_at) AS last_order
            FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
            WHERE c.email LIKE ? OR (c.first_name || ' ' || c.last_name) LIKE ?
            GROUP BY c.id ORDER BY spent DESC
            """,
            (like, like),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["segment"] = segment(d["spent"], d["order_count"])
        out.append(d)
    return out


def customer(cid):
    for c in customers():
        if c["id"] == cid:
            return c
    return None


def orders(status=None, customer_id=None, limit=None, q=""):
    sql = (
        "SELECT o.*, c.first_name, c.last_name, c.email FROM orders o "
        "LEFT JOIN customers c ON c.id = o.customer_id WHERE 1=1"
    )
    args = []
    if status:
        sql += " AND o.status = ?"
        args.append(status)
    if customer_id:
        sql += " AND o.customer_id = ?"
        args.append(customer_id)
    if q:
        sql += " AND (CAST(o.woo_id AS TEXT) LIKE ? OR c.email LIKE ? OR (c.first_name || ' ' || c.last_name) LIKE ?)"
        like = f"%{q}%"
        args.extend((like, like, like))
    sql += " ORDER BY o.placed_at DESC"
    if limit:
        sql += " LIMIT ?"
        args.append(limit)
    with conn() as c:
        return c.execute(sql, args).fetchall()


def order_statuses():
    with conn() as c:
        return [r[0] for r in c.execute("SELECT DISTINCT status FROM orders ORDER BY 1")]


def latest_order(customer_id):
    rows = orders(customer_id=customer_id, limit=1)
    return rows[0] if rows else None


def latest_currency():
    rows = orders(limit=1)
    return rows[0]["currency"] if rows and rows[0]["currency"] else "USD"


def add_message(customer_id, order_id, template, subject, status, note):
    with conn() as c:
        c.execute(
            "INSERT INTO messages (customer_id, order_id, template, subject, status, note, sent_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (customer_id, order_id, template, subject, status, note, now()),
        )


def message_exists(order_id, template):
    with conn() as c:
        return c.execute(
            "SELECT 1 FROM messages WHERE order_id=? AND template=?", (order_id, template)
        ).fetchone() is not None


def messages(customer_id=None, limit=None):
    sql = (
        "SELECT m.*, c.first_name, c.last_name, c.email FROM messages m "
        "LEFT JOIN customers c ON c.id = m.customer_id WHERE 1=1"
    )
    args = []
    if customer_id:
        sql += " AND m.customer_id = ?"
        args.append(customer_id)
    sql += " ORDER BY m.id DESC"
    if limit:
        sql += " LIMIT ?"
        args.append(limit)
    with conn() as c:
        return c.execute(sql, args).fetchall()


def stats():
    with conn() as c:
        repeat = c.execute(
            "SELECT COUNT(*) FROM (SELECT customer_id FROM orders GROUP BY customer_id HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        count = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        revenue = c.execute("SELECT COALESCE(SUM(total),0) FROM orders").fetchone()[0]
        return {
            "customers": c.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
            "orders": count,
            "revenue": revenue,
            "average_order": revenue / count if count else 0,
            "repeat_customers": repeat,
            "messages": c.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
        }


def monthly_revenue(months=6):
    from datetime import date
    totals = {}
    with conn() as c:
        for month, value in c.execute(
            "SELECT substr(placed_at,1,7), COALESCE(SUM(total),0) FROM orders GROUP BY substr(placed_at,1,7)"
        ):
            totals[month] = float(value or 0)
    current = date.today().replace(day=1)
    keys = []
    for offset in reversed(range(months)):
        year, month = current.year, current.month - offset
        while month <= 0:
            year -= 1
            month += 12
        keys.append(date(year, month, 1))
    maximum = max((totals.get(m.strftime("%Y-%m"), 0) for m in keys), default=0)
    return [
        {"label": m.strftime("%b"), "month": m.strftime("%Y-%m"),
         "total": totals.get(m.strftime("%Y-%m"), 0),
         "height": max(7, round(totals.get(m.strftime("%Y-%m"), 0) / maximum * 100)) if maximum else 7}
        for m in keys
    ]
