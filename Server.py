import os
import httpx
from mcp.server.fastmcp import FastMCP

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
def technician_tickets(user_id: int, status: str = "", created_after: str = "",
                       page: int = 1) -> dict:
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
def create_customer(firstname: str, lastname: str, phone: str,
                    address: str, city: str, state: str, zip: str,
                    referred_by: str = "") -> dict:
    """Create a customer. Address is required by RepairShopr."""
    return post("/customers", {
        "firstname": firstname, "lastname": lastname, "phone": phone,
        "address": address, "city": city, "state": state, "zip": zip,
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
        "customer_id": customer_id, "subject": subject,
        "problem_type": "Other", "description": problem,
        "comments_attributes": comments,
    })
