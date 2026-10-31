import os
import time
from datetime import date, timedelta
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

API_KEY = os.environ["REPAIRSHOPR_API_KEY"].strip()
SECRET = os.environ["MCP_SECRET_PATH"]
BASE = "https://techmediagroup.repairshopr.com/api/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}

mcp = FastMCP("repairshopr", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
mcp.settings.streamable_http_path = f"/{SECRET}"


def get(path, params=None):
    r = httpx.get(f"{BASE}{path}", headers=HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def post(path, data):
    r = httpx.post(f"{BASE}{path}", headers=HEADERS, json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def put(path, data):
    r = httpx.put(f"{BASE}{path}", headers=HEADERS, json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def ticket_id_from_number(number):
    data = get("/tickets", {"number": number})
    for t in data.get("tickets", []):
        if str(t.get("number")) == str(number):
            return t["id"]
    raise ValueError(f"Ticket {number} not found")


@mcp.tool()
def search_customers(query: str) -> dict:
    """Search customers by name, phone, or email."""
    return get("/customers", {"query": query})


@mcp.tool()
def search_tickets(query: str, page: int = 1) -> dict:
    """Search tickets by number, customer name, or keyword. 50 per page; use page for more."""
    return get("/tickets", {"query": query, "page": page})


@mcp.tool()
def list_technicians() -> dict:
    """List all technicians (RepairShopr users) with their names and user IDs."""
    return get("/users")


@mcp.tool()
def technician_tickets(user_id: int, status: str = "", created_after: str = "", page: int = 1) -> dict:
    """Tickets assigned to one technician. Get user_id from list_technicians.
    status examples: 'Not Closed', 'New', 'In Progress', 'Waiting for Parts', 'Resolved'.
    created_after format: YYYY-MM-DD. 50 per page; use page for more."""
    params = {"user_id": user_id, "page": page}
    if status:
        params["status"] = status
    if created_after:
        params["created_after"] = created_after
    return get("/tickets", params)


@mcp.tool()
def create_customer(firstname: str, lastname: str, phone: str, address: str, city: str,
                    state: str, zip: str, referred_by: str = "") -> dict:
    """Create a customer. Address is required by RepairShopr."""
    return post("/customers", {
        "firstname": firstname,
        "lastname": lastname,
        "phone": phone,
        "address": address,
        "city": city,
        "state": state,
        "zip": zip,
        "referred_by": referred_by,
    })


@mcp.tool()
def create_ticket(customer_id: int, subject: str, problem: str,
                  private_note: str = "", public_note: str = "") -> dict:
    """Create a repair ticket. Subject = make/model/serial, problem = the issue."""
    comments = []
    if public_note:
        comments.append({"subject": "Intake", "body": public_note, "hidden": False})
    if private_note:
        comments.append({"subject": "Intake (private)", "body": private_note, "hidden": True})
    return post("/tickets", {
        "customer_id": customer_id,
        "subject": subject,
        "problem_type": "Other",
        "description": problem,
        "comments_attributes": comments,
    })


@mcp.tool()
def add_ticket_note(ticket_number: str, note: str, private: bool = True, subject: str = "Update") -> dict:
    """Add a note to a ticket by its work order number (e.g. 59589).
    private=True (default) hides it from the customer and sends no email.
    private=False makes it a public note the customer can see."""
    tid = ticket_id_from_number(ticket_number)
    return post(f"/tickets/{tid}/comment", {
        "subject": subject,
        "body": note,
        "hidden": private,
        "do_not_email": private,
    })


@mcp.tool()
def delete_ticket_note(ticket_number: str, comment_id: int) -> dict:
    """Delete a note from a ticket by work order number and comment id.
    Only use when Andy explicitly says to delete a specific note."""
    tid = ticket_id_from_number(ticket_number)
    r = httpx.delete(f"{BASE}/tickets/{tid}/comments/{comment_id}", headers=HEADERS, timeout=30)
    return {"status": r.status_code, "body": r.text}


@mcp.tool()
def update_ticket_status(ticket_number: str, status: str) -> dict:
    """Change a ticket's status by work order number. Use the exact status names from
    RepairShopr, e.g. 'New', 'In Progress', 'Waiting for Parts', 'Customer Reply', 'Resolved'."""
    tid = ticket_id_from_number(ticket_number)
    return put(f"/tickets/{tid}", {"status": status})


@mcp.tool()
def list_invoices(since_date: str = "", unpaid_only: bool = False, page: int = 1) -> dict:
    """List invoices. since_date format YYYY-MM-DD. Shows totals, paid status, ticket link."""
    params = {"page": page}
    if since_date:
        params["since_updated_at"] = since_date
    if unpaid_only:
        params["unpaid"] = "true"
    return get("/invoices", params)


@mcp.tool()
def get_invoice(invoice_id: int) -> dict:
    """Full details of one invoice, including line items."""
    return get(f"/invoices/{invoice_id}")


@mcp.tool()
def list_payments(page: int = 1) -> dict:
    """List customer payments received."""
    return get("/payments", {"page": page})


@mcp.tool()
def list_estimates(page: int = 1) -> dict:
    """List estimates with amounts and status."""
    return get("/estimates", {"page": page})


@mcp.tool()
def technician_revenue(user_id: int, start_date: str, end_date: str = "") -> dict:
    """Total invoiced money for one technician's tickets in a date range (YYYY-MM-DD)."""
    ticket_ids, page = set(), 1
    while True:
        data = get("/tickets", {"user_id": user_id, "created_after": start_date, "page": page})
        for t in data.get("tickets", []):
            ticket_ids.add(t["id"])
        if page >= data.get("meta", {}).get("total_pages", 1):
            break
        page += 1
    invoices, page = [], 1
    while True:
        data = get("/invoices", {"since_updated_at": start_date, "page": page})
        for inv in data.get("invoices", []):
            d = (inv.get("date") or "")[:10]
            if inv.get("ticket_id") in ticket_ids and (not end_date or d <= end_date):
                invoices.append({
                    "number": inv.get("number"),
                    "customer": inv.get("customer_business_then_name"),
                    "date": d,
                    "total": float(inv.get("total") or 0),
                    "paid": inv.get("is_paid"),
                })
        if page >= data.get("meta", {}).get("total_pages", 1):
            break
        page += 1
    return {
        "invoice_count": len(invoices),
        "total_invoiced": round(sum(i["total"] for i in invoices), 2),
        "invoices": invoices,
    }


# ---------- Inventory (add items from a photo) ----------

@mcp.tool()
def search_products(query: str, page: int = 1) -> dict:
    """Search inventory products by name, SKU, or UPC barcode.
    Use before create_product to avoid duplicates."""
    return get("/products", {"query": query, "page": page})


@mcp.tool()
def create_product(name: str, description: str = "", upc_code: str = "",
                   price_cost: float = 0, price_retail: float = 0,
                   quantity: int = 1, physical_location: str = "",
                   notes: str = "") -> dict:
    """Add an item to RepairShopr inventory. Usually filled in from a photo
    of the item or its label: name = make/model, upc_code = barcode number."""
    return post("/products", {
        "name": name,
        "description": description or name,
        "upc_code": upc_code,
        "price_cost": price_cost,
        "price_retail": price_retail,
        "maintain_stock": True,
        "quantity": quantity,
        "physical_location": physical_location,
        "notes": notes,
    })


@mcp.tool()
def update_product(product_id: int, name: str = None, description: str = None,
                   upc_code: str = None, price_cost: float = None,
                   price_retail: float = None, quantity: int = None,
                   physical_location: str = None, notes: str = None) -> dict:
    """Edit an inventory item. Get product_id from search_products.
    Only the fields you pass are changed; everything else stays the same."""
    fields = {
        "name": name,
        "description": description,
        "upc_code": upc_code,
        "price_cost": price_cost,
        "price_retail": price_retail,
        "quantity": quantity,
        "physical_location": physical_location,
        "notes": notes,
    }
    data = {k: v for k, v in fields.items() if v is not None}
    if not data:
        raise ValueError("Nothing to update")
    return put(f"/products/{product_id}", data)


@mcp.tool()
def delete_product(product_id: int) -> dict:
    """Delete an inventory item. Get product_id from search_products.
    Only use when Andy explicitly says to delete a specific item.
    If RepairShopr won't allow a hard delete, the item is disabled instead."""
    r = httpx.delete(f"{BASE}/products/{product_id}", headers=HEADERS, timeout=30)
    if r.status_code < 300:
        return {"result": "deleted", "status": r.status_code}
    d = httpx.put(f"{BASE}/products/{product_id}", headers=HEADERS,
                  json={"disabled": True}, timeout=30)
    return {"result": "disabled" if d.status_code < 300 else "failed",
            "delete_status": r.status_code, "disable_status": d.status_code, "body": d.text}


@mcp.tool()
def zero_out_old_inventory(months: int = 6, dry_run: bool = True, max_items: int = 200) -> dict:
    """Bulk clean-up: set quantity to 0 and put 'DELETED' in front of the name for every
    product not updated in `months` months. Run with dry_run=True first to see the count.
    max_items caps how many are changed per run; run again until remaining is 0."""
    cutoff = (date.today() - timedelta(days=30 * months)).isoformat()

    old, page = [], 1
    while True:
        res = get("/products", {"page": page})
        for p in res.get("products", []):
            name = (p.get("name") or "").strip()
            if name.startswith("DELETED"):
                continue
            updated = (p.get("since_updated_at") or "")[:10]
            if updated and updated < cutoff:
                old.append((p["id"], name))
        if page >= res.get("meta", {}).get("total_pages", 1):
            break
        page += 1
        time.sleep(0.35)  # stay under RepairShopr's rate limit

    if dry_run:
        return {"cutoff": cutoff, "would_change": len(old), "sample": [n for _, n in old[:10]]}

    done, failed = 0, []
    for pid, name in old[:max_items]:
        try:
            put(f"/products/{pid}", {"quantity": 0, "name": f"DELETED {name}"})
            done += 1
        except Exception as e:
            failed.append({"id": pid, "error": str(e)})
        time.sleep(0.35)

    return {"changed": done, "failed": len(failed),
            "remaining": max(0, len(old) - max_items), "errors": failed[:5]}


# ---------- Vapi caller greeting (looks up caller before the AI answers) ----------

GREETING = "thank you for calling Tek Media Group, this call may be recorded for quality purposes. To confirm your account, can you please tell me your last name?."


def find_customer_by_phone(number):
    digits = "".join(ch for ch in number if ch.isdigit())[-10:]
    if len(digits) != 10:
        return None
    tries = (digits, f"{digits[:3]}-{digits[3:6]}-{digits[6:]}", f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
    for q in tries:
        try:
            data = get("/customers", {"query": q})
        except Exception:
            continue
        for c in data.get("customers", []):
            for p in (c.get("phone") or "", c.get("mobile") or ""):
                if "".join(ch for ch in p if ch.isdigit())[-10:] == digits:
                    return c
    return None


@mcp.custom_route(f"/{SECRET}/vapi", methods=["POST"])
async def vapi_assistant_request(request: Request):
    body = await request.json()
    msg = body.get("message", {})
    number = ((msg.get("call") or {}).get("customer") or {}).get("number", "")
    c = find_customer_by_phone(number) if number else None
    if c:
        name = c.get("business_name") or (c.get("firstname") or "").strip()
        first = f"Hello, {name}, {GREETING}"
        values = {"customer_name": name, "customer_id": str(c.get("id")), "customer_lastname": c.get("lastname") or ""}
    else:
        first = "Thank you for calling Tek Media Group, this call may be recorded for quality purposes."
        values = {"customer_name": "", "customer_id": "", "customer_lastname": ""}
    return JSONResponse({
        "assistantId": os.environ["VAPI_ASSISTANT_ID"],
        "assistantOverrides": {
            "firstMessage": first,
            "firstMessageMode": "assistant-speaks-first",
            "variableValues": values,
        },
    })


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
