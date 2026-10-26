import os
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
