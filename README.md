# Order-to-Cash Graph Explorer

A context graph system with LLM-powered natural language query interface 
built on SAP Order-to-Cash data.

## Live Demo
[https://order-to-cash-snowy.vercel.app/](https://order-to-cash-snowy.vercel.app/)

## Architecture

### Database Choice — SQLite
Chose SQLite over a graph database (Neo4j) because:
- The dataset fits entirely in memory (21,474 rows)
- SQL joins naturally express the O2C relationships
- Zero infrastructure overhead — DB travels with the code
- LLMs generate SQL reliably; Cypher query generation is less mature

### Graph Modeling
7 node types: Customer, SalesOrder, Product, Delivery, 
BillingDocument, JournalEntry, Payment.

Key insight discovered during modeling: 
`billing_document_items.referenceSdDocument` stores the delivery 
document number (807xxxxx range), NOT the sales order. This required 
a two-hop join: BillingDoc → Delivery → SalesOrder.

### LLM Prompting Strategy — Two-Call Pattern
**Call 1 (Text→SQL):** Schema + question → SQL only.
Temperature=0 for deterministic query generation.

**Call 2 (Results→English):** Raw data rows → plain English answer.
Temperature=0.3 for natural language variation.

Separated into two calls because SQL generation and result 
interpretation are different cognitive tasks — mixing them degrades 
both.

### Guardrails — Two Layers
**Layer 1:** Python keyword filter — checks for 35+ business domain 
terms before making any LLM call. Rejects instantly, no API cost.

**Layer 2:** System prompt instruction — LLM told to return a 
specific rejection message for off-topic questions even if 
Layer 1 passes.

### Auto-Fix Loop
If generated SQL fails execution, the error is sent back to the LLM 
for one self-correction attempt. Handles ~90% of SQL errors.

## Tech Stack
- **Backend:** Python, FastAPI, SQLite, NetworkX, Groq (LLaMA 3.3 70B)
- **Frontend:** React, Vite, react-force-graph-2d, Axios
- **Deployment:** Railway (backend), Vercel (frontend)

## Running Locally

### Backend
```bash
cd backend
pip install -r requirements.txt
python load_db.py      # load data into SQLite
python graph.py        # build graph
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Dataset
SAP Order-to-Cash data with 19 entity types, 21,474 rows total.
Full flow: Sales Order → Delivery → Billing Document → 
Journal Entry → Payment