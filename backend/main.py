import os
import json
import sqlite3
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from graph import build_graph, graph_to_json
from llm import answer_question

# ── Load environment variables from .env file ──────────────────────────────
load_dotenv()

# ── App setup ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Order-to-Cash Graph API",
    description="Graph-based query system for SAP Order-to-Cash data",
    version="1.0.0"
)

# ── CORS — allow React frontend to call this server ────────────────────────
# Without this the browser blocks all requests from localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins for the demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent
DB_PATH    = BASE_DIR / "database.db"
GRAPH_PATH = BASE_DIR / "graph_data.json"

# ── Build graph once on startup ────────────────────────────────────────────
# We build it when the server starts and cache it in memory.
# This means every request gets the graph instantly —
# no need to rebuild from the database every time.
print("Building graph on startup...")
_graph = build_graph()
_graph_json = graph_to_json(_graph)

# Save fresh copy to disk as well
with open(GRAPH_PATH, "w") as f:
    json.dump(_graph_json, f)
print(f"Graph ready: {len(_graph_json['nodes'])} nodes, {len(_graph_json['edges'])} edges")

# ── Request/Response models ────────────────────────────────────────────────
# Pydantic models define exactly what shape the JSON must be.
# FastAPI validates incoming requests automatically against these.

class QueryRequest(BaseModel):
    question: str          # the user's natural language question

class QueryResponse(BaseModel):
    answer: str            # plain English answer
    sql: str               # the SQL that was generated (for transparency)
    node_ids: list[str]    # graph node IDs to highlight in the UI

# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    """Health check — confirms the server is running."""
    return {
        "status": "ok",
        "message": "Order-to-Cash API is running",
        "endpoints": ["/api/graph", "/api/query", "/api/stats", "/docs"]
    }

@app.get("/api/graph")
def get_graph(type: str = None, search: str = None):
    """
    Returns the full graph as JSON.
    
    Optional query parameters:
    - ?type=SalesOrder     → filter nodes to only this entity type
    - ?search=740506       → filter nodes whose label contains this string
    
    The frontend calls this on page load to render the visualization.
    Example: GET /api/graph
    Example: GET /api/graph?type=Customer
    Example: GET /api/graph?search=740506
    """
    nodes = _graph_json["nodes"]
    edges = _graph_json["edges"]

    # Apply type filter if provided
    if type:
        nodes = [n for n in nodes if n.get("type") == type]
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in edges
                 if e["source"] in node_ids and e["target"] in node_ids]

    # Apply search filter if provided
    if search:
        search_lower = search.lower()
        nodes = [n for n in nodes
                 if search_lower in n.get("label", "").lower()
                 or search_lower in n.get("id", "").lower()]
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in edges
                 if e["source"] in node_ids and e["target"] in node_ids]

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges)
    }

@app.get("/api/graph/node/{node_id}")
def get_node(node_id: str):
    """
    Returns full metadata for a single node by its ID.
    Called when a user clicks a node in the visualization.
    Example: GET /api/graph/node/SO_740506
    """
    for node in _graph_json["nodes"]:
        if node["id"] == node_id:
            # Also return all connected node IDs (neighbors)
            neighbors = []
            for edge in _graph_json["edges"]:
                if edge["source"] == node_id:
                    neighbors.append({"id": edge["target"], "relation": edge["relation"], "direction": "out"})
                elif edge["target"] == node_id:
                    neighbors.append({"id": edge["source"], "relation": edge["relation"], "direction": "in"})
            return {"node": node, "neighbors": neighbors}

    raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

@app.post("/api/query", response_model=QueryResponse)
def query(request: QueryRequest):
    """
    Main chat endpoint. Accepts a natural language question,
    returns a data-backed answer.
    
    Request body:  { "question": "which products have the most billing docs?" }
    Response body: { "answer": "...", "sql": "...", "node_ids": [...] }
    """
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    # Pass to LLM engine (stub in Step 4, real in Step 5)
    result = answer_question(question)

    return QueryResponse(
        answer=result.get("answer", ""),
        sql=result.get("sql", ""),
        node_ids=result.get("node_ids", [])
    )

@app.get("/api/stats")
def get_stats():
    """
    Returns summary statistics about the dataset.
    Useful for the UI dashboard and for verifying data is loaded.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    stats = {}

    tables = [
        "sales_order_headers",
        "outbound_delivery_headers",
        "billing_document_headers",
        "journal_entry_items_accounts_receivable",
        "payments_accounts_receivable",
        "business_partners",
        "products"
    ]

    for table in tables:
        try:
            count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            stats[table] = count
        except Exception:
            stats[table] = 0

    # Extra business insights
    try:
        stats["total_order_value"] = conn.execute(
            "SELECT ROUND(SUM(totalNetAmount), 2) FROM sales_order_headers"
        ).fetchone()[0]

        stats["cancelled_billing_docs"] = conn.execute(
            "SELECT COUNT(*) FROM billing_document_cancellations"
        ).fetchone()[0]

        stats["uncleared_journal_entries"] = conn.execute("""
            SELECT COUNT(DISTINCT accountingDocument)
            FROM journal_entry_items_accounts_receivable
            WHERE clearingDate IS NULL OR clearingDate = ''
        """).fetchone()[0]
    except Exception:
        pass

    conn.close()
    stats["graph_nodes"] = len(_graph_json["nodes"])
    stats["graph_edges"] = len(_graph_json["edges"])
    return stats