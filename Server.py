import os
import httpx
from mcp.server.fastmcp import FastMCP

API_KEY = os.environ["REPAIRSHOPR_API_KEY"]
SECRET = os.environ["MCP_SECRET_PATH"]
BASE = "https://tekmediagroup.repairshopr.com/api/v1"
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
def search_tickets(query: str) -> dict:
    """Search tickets by number, customer name, or keyword."""
    return get("/tickets", {"query": query})

@mcp.tool()
def get_ticket(ticket_id: int) -> dict:
    """Get full details of one ticket by its ID."""
    return get(f"/tickets/{ticket_id}")

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

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
