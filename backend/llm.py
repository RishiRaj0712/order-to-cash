import os
import re
import sqlite3
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

DB_PATH = "./database.db"

# ── Groq client ────────────────────────────────────────────────────────────
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL  = "llama-3.3-70b-versatile"

# ── Guardrail keywords ─────────────────────────────────────────────────────
# If NONE of these appear in the question, we reject immediately.
DOMAIN_KEYWORDS = [
    "order", "delivery", "deliveries", "billing", "bill", "invoice",
    "payment", "customer", "product", "material", "plant", "journal",
    "amount", "sales", "document", "shipment", "quantity", "price",
    "cancell", "status", "vendor", "supplier", "account", "fiscal",
    "revenue", "charge", "credit", "debit", "dispatch", "freight",
    "item", "schedule", "flow", "trace", "track", "outstanding",
    "cleared", "uncleared", "receivable", "payable", "gl", "entry"
]

# ── Full database schema for the LLM ──────────────────────────────────────
# This tells the LLM exactly what tables and columns exist.
# The more precise this is, the better the SQL it generates.
SCHEMA = """
You have access to a SQLite database with these tables:

TABLE sales_order_headers:
  salesOrder (TEXT) — unique sales order ID e.g. 740506
  soldToParty (TEXT) — customer ID, links to business_partners.customer
  totalNetAmount (REAL) — total order value
  transactionCurrency (TEXT) — currency e.g. INR
  overallDeliveryStatus (TEXT) — C=complete, A=not started, B=partial
  overallOrdReltdBillgStatus (TEXT) — billing status
  creationDate (TEXT) — when order was created
  salesOrderType (TEXT) — order type e.g. OR=standard

TABLE sales_order_items:
  salesOrder (TEXT) — links to sales_order_headers.salesOrder
  salesOrderItem (TEXT) — line item number
  material (TEXT) — product ID, links to products.product
  requestedQuantity (REAL) — quantity ordered
  netAmount (REAL) — line item value
  productionPlant (TEXT) — plant ID

TABLE sales_order_schedule_lines:
  salesOrder (TEXT) — links to sales_order_headers.salesOrder
  salesOrderItem (TEXT) — line item number
  confirmedDeliveryDate (TEXT) — confirmed delivery date

TABLE outbound_delivery_headers:
  deliveryDocument (TEXT) — unique delivery ID e.g. 80738076
  overallGoodsMovementStatus (TEXT) — C=goods issued, A=not started
  overallPickingStatus (TEXT) — picking status
  creationDate (TEXT) — delivery creation date
  shippingPoint (TEXT) — shipping location

TABLE outbound_delivery_items:
  deliveryDocument (TEXT) — links to outbound_delivery_headers.deliveryDocument
  referenceSdDocument (TEXT) — SALES ORDER ID that this delivery fulfills
  actualDeliveryQuantity (REAL) — quantity delivered
  plant (TEXT) — plant ID
  storageLocation (TEXT) — storage location

TABLE billing_document_headers:
  billingDocument (TEXT) — unique billing/invoice ID e.g. 90504298
  totalNetAmount (REAL) — invoice amount
  billingDocumentDate (TEXT) — invoice date
  accountingDocument (TEXT) — links to journal_entry_items_accounts_receivable.accountingDocument
  soldToParty (TEXT) — customer ID
  billingDocumentIsCancelled (TEXT) — True if cancelled
  transactionCurrency (TEXT) — currency

TABLE billing_document_items:
  billingDocument (TEXT) — links to billing_document_headers.billingDocument
  material (TEXT) — product ID
  billingQuantity (REAL) — quantity billed
  netAmount (REAL) — line item amount
  referenceSdDocument (TEXT) — DELIVERY DOCUMENT ID (NOT sales order)

TABLE billing_document_cancellations:
  billingDocument (TEXT) — the cancellation document ID
  cancelledBillingDocument (TEXT) — the original billing doc that was cancelled
  totalNetAmount (REAL) — amount of cancelled invoice

TABLE journal_entry_items_accounts_receivable:
  accountingDocument (TEXT) — unique journal entry ID
  referenceDocument (TEXT) — BILLING DOCUMENT ID this entry is for
  glAccount (TEXT) — GL account number
  amountInTransactionCurrency (REAL) — amount (negative = debit)
  postingDate (TEXT) — when entry was posted
  customer (TEXT) — customer ID
  clearingDate (TEXT) — date payment was cleared (NULL if unpaid)
  clearingAccountingDocument (TEXT) — payment doc that cleared this entry

TABLE payments_accounts_receivable:
  accountingDocument (TEXT) — unique payment ID
  clearingAccountingDocument (TEXT) — journal entry ID this payment clears
  amountInTransactionCurrency (REAL) — payment amount
  postingDate (TEXT) — payment date
  customer (TEXT) — customer ID

TABLE business_partners:
  businessPartner (TEXT) — business partner ID
  customer (TEXT) — customer ID (same value, use this to join)
  businessPartnerFullName (TEXT) — company name
  businessPartnerName (TEXT) — short name

TABLE business_partner_addresses:
  businessPartner (TEXT) — links to business_partners.businessPartner
  cityName (TEXT) — city
  country (TEXT) — country code

TABLE products:
  product (TEXT) — unique product ID
  productType (TEXT) — type code
  productGroup (TEXT) — product group
  grossWeight (REAL) — weight
  division (TEXT) — division code

TABLE product_descriptions:
  product (TEXT) — links to products.product
  productDescription (TEXT) — readable product name e.g. "BODYSPRAY ACTIVE+BOLD"

TABLE plants:
  plant (TEXT) — unique plant ID
  plantName (TEXT) — plant name e.g. "Lake Christopher Plant"
  salesOrganization (TEXT) — sales org

TABLE product_plants:
  product (TEXT) — product ID
  plant (TEXT) — plant ID
  profitCenter (TEXT) — profit center

KEY RELATIONSHIPS (use these for JOINs):
- sales_order_headers.soldToParty = business_partners.customer
- sales_order_items.salesOrder = sales_order_headers.salesOrder
- sales_order_items.material = products.product = product_descriptions.product
- outbound_delivery_items.referenceSdDocument = sales_order_headers.salesOrder
- outbound_delivery_items.deliveryDocument = outbound_delivery_headers.deliveryDocument
- billing_document_items.referenceSdDocument = outbound_delivery_headers.deliveryDocument
- billing_document_items.billingDocument = billing_document_headers.billingDocument
- billing_document_headers.accountingDocument = journal_entry_items_accounts_receivable.accountingDocument
- billing_document_headers.billingDocument = journal_entry_items_accounts_receivable.referenceDocument
- journal_entry_items_accounts_receivable.accountingDocument = payments_accounts_receivable.clearingAccountingDocument

IMPORTANT NOTES:
- billing_document_items.referenceSdDocument is a DELIVERY document number (80xxxxxxx range), NOT a sales order
- outbound_delivery_items.referenceSdDocument IS the sales order number (74xxxx range)
- amounts in journal entries can be negative (debits); use ABS() when summing
- billingDocumentIsCancelled = 'True' means cancelled
- overallDeliveryStatus 'C' = complete, 'A' = not started, 'B' = partial
"""

# ── SQL Text-to-SQL prompt ─────────────────────────────────────────────────
SQL_SYSTEM_PROMPT = f"""You are an expert SQLite query writer for a SAP Order-to-Cash business system.

{SCHEMA}

RULES:
1. Return ONLY a valid SQLite SQL query — no explanation, no markdown, no backticks
2. Always use table aliases for clarity (e.g. soh for sales_order_headers)
3. Use LIMIT 50 unless the user asks for all results
4. Use CAST(x AS TEXT) when comparing IDs across tables to avoid type mismatches  
5. For product names always JOIN product_descriptions on product
6. For customer names always JOIN business_partners on customer = soldToParty
7. Never use columns that don't exist in the schema above
8. If the question cannot be answered with SQL on this dataset, return: SELECT 'insufficient_data' as result
"""

# ── Answer formatting prompt ───────────────────────────────────────────────
ANSWER_SYSTEM_PROMPT = """You are a concise business analyst presenting data insights.

Given a user's question and SQL query results, write a direct, sharp answer.

STRICT RULES:
1. Lead with the number or key fact — never with "Based on the data..."
2. Never explain what you did ("I queried...", "This represents the sum of...")
3. Never reference the database, tables, or dataset in your answer
4. Never add meta-commentary like "as per the records" or "in the system"
5. If it's a single number, one sentence is enough
6. Use INR symbol for currency, not $ — this is Indian business data
7. Round amounts to 2 decimal places
8. Keep answers under 80 words unless listing multiple items
9. This system only answers questions about the Order-to-Cash dataset.
   If the question is unrelated, respond ONLY with:
   "This system is designed to answer questions about the provided business dataset only."

GOOD example:
Q: What is the total value of all cancelled billing documents?
A: Total cancelled billing value is INR 30,079.43 across 80 cancellation documents.

BAD example:
A: The total value of all cancelled billing documents is $30,079.43. This amount 
represents the sum of the total net amounts of all billing document cancellations 
in the dataset.
"""

# ── Helper functions ───────────────────────────────────────────────────────

def is_relevant_question(question: str) -> bool:
    """
    Guardrail Layer 1 — fast keyword check.
    Returns False if no business domain keywords found.
    This runs BEFORE any LLM call, saving API quota.
    """
    q_lower = question.lower()
    return any(kw in q_lower for kw in DOMAIN_KEYWORDS)

def run_sql(sql: str) -> tuple[list[dict], str | None]:
    """
    Executes a SQL query against the database.
    Returns (rows_as_dicts, error_message_or_None).
    Rows are returned as a list of dicts for easy JSON serialization.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(sql)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows, None
    except Exception as e:
        return [], str(e)

def extract_node_ids(answer: str, sql_results: list[dict]) -> list[str]:
    """
    Scans the answer text and SQL results for document numbers
    and maps them to graph node IDs for frontend highlighting.
    
    Looks for:
    - Sales orders (74xxxx range)    → SO_xxxxxx
    - Delivery docs (807xxxxx range) → DEL_xxxxxxxx
    - Billing docs (905xxxxx range)  → BILL_xxxxxxxxx
    - Journal entries (940xxxxx)     → JE_xxxxxxxxx
    - Payments (940xxxxx)            → PAY_xxxxxxxxx
    - Customer IDs (3100/3200 range) → CUST_xxxxxxxxx
    - Product IDs                    → PROD_xxxxxxxxx
    """
    node_ids = set()

    # Combine answer text + all values from SQL results into one searchable string
    search_text = answer
    for row in sql_results:
        for val in row.values():
            if val:
                search_text += " " + str(val)

    # Extract numbers that match known ID patterns
    numbers = re.findall(r'\b(\d{6,})\b', search_text)

    for num in numbers:
        n = str(num)
        if n.startswith("74"):
            node_ids.add(f"SO_{n}")
        elif n.startswith("807") or n.startswith("80"):
            node_ids.add(f"DEL_{n}")
        elif n.startswith("905") or n.startswith("906"):
            node_ids.add(f"BILL_{n}")
        elif n.startswith("940"):
            node_ids.add(f"JE_{n}")
            node_ids.add(f"PAY_{n}")
        elif n.startswith("310") or n.startswith("320"):
            node_ids.add(f"CUST_{n}")

    # Also check for product IDs directly in SQL results
    for row in sql_results:
        for key, val in row.items():
            if key in ("material", "product") and val:
                node_ids.add(f"PROD_{val}")

    return list(node_ids)[:20]  # cap at 20 highlighted nodes

def generate_sql(question: str) -> tuple[str, str | None]:
    """
    LLM Call 1 — converts natural language question to SQL.
    Returns (sql_string, error_or_None).
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SQL_SYSTEM_PROMPT},
            {"role": "user",   "content": f"Write a SQL query to answer: {question}"}
        ],
        temperature=0,      # 0 = deterministic, best for SQL generation
        max_tokens=500
    )
    sql = response.choices[0].message.content.strip()

    # Strip markdown code fences if the LLM added them despite instructions
    sql = re.sub(r"```sql|```", "", sql).strip()
    return sql, None

def format_answer(question: str, sql: str, results: list[dict]) -> str:
    """
    LLM Call 2 — converts raw SQL results into a plain English answer.
    """
    results_str = json.dumps(results[:20], indent=2)  # cap at 20 rows for prompt size

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content":
                f"Question: {question}\n\nSQL used:\n{sql}\n\nResults:\n{results_str}\n\nWrite a clear answer:"}
        ],
        temperature=0.3,    # slight creativity for natural language
        max_tokens=300
    )
    return response.choices[0].message.content.strip()

# ── Main entry point ───────────────────────────────────────────────────────

def answer_question(question: str) -> dict:
    """
    Full pipeline:
    1. Guardrail check — reject off-topic questions instantly
    2. LLM Call 1 — generate SQL from question
    3. Execute SQL — run against SQLite
    4. Auto-fix — if SQL errors, try once to fix it
    5. LLM Call 2 — format results as English
    6. Extract node IDs — for graph highlighting
    """

    # ── Step 1: Guardrail ──────────────────────────────────────────────────
    if not is_relevant_question(question):
        return {
            "answer": "This system is designed to answer questions about the provided business dataset only. Please ask about orders, deliveries, billing documents, payments, customers, or products.",
            "sql": "",
            "node_ids": []
        }

    # ── Step 2: Generate SQL ───────────────────────────────────────────────
    sql, err = generate_sql(question)
    if err:
        return {"answer": f"Error generating query: {err}", "sql": "", "node_ids": []}

    # ── Step 3: Execute SQL ────────────────────────────────────────────────
    results, sql_error = run_sql(sql)

    # ── Step 4: Auto-fix if SQL failed ────────────────────────────────────
    if sql_error:
        print(f"  SQL error: {sql_error} — attempting auto-fix...")
        fix_prompt = f"""The following SQL query failed with error: {sql_error}

Original query:
{sql}

Fix the query and return ONLY the corrected SQL, nothing else."""

        fix_response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SQL_SYSTEM_PROMPT},
                {"role": "user",   "content": fix_prompt}
            ],
            temperature=0,
            max_tokens=500
        )
        sql = re.sub(r"```sql|```", "", fix_response.choices[0].message.content).strip()
        results, sql_error = run_sql(sql)

        if sql_error:
            return {
                "answer": "I was unable to generate a valid query for that question. Please try rephrasing.",
                "sql": sql,
                "node_ids": []
            }

    # ── Step 5: Handle empty results ──────────────────────────────────────
    if not results:
        return {
            "answer": "No data found matching your query. This may indicate a broken flow or data gap in the dataset.",
            "sql": sql,
            "node_ids": []
        }

    # Check for insufficient_data sentinel
    if results == [{"result": "insufficient_data"}]:
        return {
            "answer": "This system is designed to answer questions about the provided business dataset only.",
            "sql": sql,
            "node_ids": []
        }

    # ── Step 6: Format answer ──────────────────────────────────────────────
    answer = format_answer(question, sql, results)

    # ── Step 7: Extract node IDs for graph highlighting ───────────────────
    node_ids = extract_node_ids(answer, results)

    return {
        "answer": answer,
        "sql": sql,
        "node_ids": node_ids
    }


# ── Test directly ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_questions = [
        "Which products are associated with the most billing documents?",
        "How many sales orders were fully delivered?",
        "Which customer placed the most orders?",
        "Write me a poem about flowers",   # should be rejected by guardrail
    ]

    for q in test_questions:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        result = answer_question(q)
        print(f"A: {result['answer']}")
        print(f"SQL: {result['sql'][:100]}..." if result['sql'] else "SQL: none")
        print(f"Nodes: {result['node_ids'][:5]}")
        