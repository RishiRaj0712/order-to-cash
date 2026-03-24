import sqlite3
import json
import networkx as nx
from collections import defaultdict

DB_PATH = "./database.db"

# ── Connect ────────────────────────────────────────────────────────────────

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name
    return conn

# ── Node builders ──────────────────────────────────────────────────────────
# Each function adds one type of node to the graph.
# We store all useful metadata on the node so the frontend
# can display it when a user clicks on it.

def add_customer_nodes(G, conn):
    rows = conn.execute("""
        SELECT bp.businessPartner, bp.businessPartnerFullName,
               bp.businessPartnerName, bpa.cityName, bpa.country
        FROM business_partners bp
        LEFT JOIN business_partner_addresses bpa
               ON bpa.businessPartner = bp.businessPartner
    """).fetchall()

    for r in rows:
        node_id = f"CUST_{r['businessPartner']}"
        G.add_node(node_id,
            type="Customer",
            label=r['businessPartnerFullName'] or r['businessPartnerName'] or node_id,
            city=r['cityName'] or "",
            country=r['country'] or "",
            entity="Customer"
        )
    print(f"  Added {len(rows)} Customer nodes")

def add_sales_order_nodes(G, conn):
    rows = conn.execute("""
        SELECT salesOrder, soldToParty, totalNetAmount,
               overallDeliveryStatus, overallOrdReltdBillgStatus,
               creationDate, transactionCurrency
        FROM sales_order_headers
    """).fetchall()

    for r in rows:
        node_id = f"SO_{r['salesOrder']}"
        G.add_node(node_id,
            type="SalesOrder",
            label=f"SO {r['salesOrder']}",
            salesOrder=str(r['salesOrder']),
            amount=r['totalNetAmount'],
            currency=r['transactionCurrency'] or "INR",
            deliveryStatus=r['overallDeliveryStatus'] or "",
            billingStatus=r['overallOrdReltdBillgStatus'] or "",
            creationDate=str(r['creationDate'] or ""),
            entity="SalesOrder"
        )
    print(f"  Added {len(rows)} SalesOrder nodes")

def add_product_nodes(G, conn):
    rows = conn.execute("""
        SELECT p.product, p.productType, p.productGroup,
               pd.productDescription
        FROM products p
        LEFT JOIN product_descriptions pd ON pd.product = p.product
    """).fetchall()

    for r in rows:
        node_id = f"PROD_{r['product']}"
        G.add_node(node_id,
            type="Product",
            label=r['productDescription'] or r['product'],
            product=str(r['product']),
            productType=r['productType'] or "",
            productGroup=r['productGroup'] or "",
            entity="Product"
        )
    print(f"  Added {len(rows)} Product nodes")

def add_delivery_nodes(G, conn):
    rows = conn.execute("""
        SELECT deliveryDocument, overallGoodsMovementStatus,
               overallPickingStatus, creationDate, shippingPoint
        FROM outbound_delivery_headers
    """).fetchall()

    for r in rows:
        node_id = f"DEL_{r['deliveryDocument']}"
        G.add_node(node_id,
            type="Delivery",
            label=f"Delivery {r['deliveryDocument']}",
            deliveryDocument=str(r['deliveryDocument']),
            goodsMovementStatus=r['overallGoodsMovementStatus'] or "",
            pickingStatus=r['overallPickingStatus'] or "",
            creationDate=str(r['creationDate'] or ""),
            entity="Delivery"
        )
    print(f"  Added {len(rows)} Delivery nodes")

def add_billing_nodes(G, conn):
    rows = conn.execute("""
        SELECT billingDocument, totalNetAmount, billingDocumentDate,
               accountingDocument, soldToParty, transactionCurrency,
               billingDocumentIsCancelled
        FROM billing_document_headers
    """).fetchall()

    for r in rows:
        node_id = f"BILL_{r['billingDocument']}"
        G.add_node(node_id,
            type="BillingDocument",
            label=f"Bill {r['billingDocument']}",
            billingDocument=str(r['billingDocument']),
            amount=r['totalNetAmount'],
            currency=r['transactionCurrency'] or "INR",
            accountingDocument=str(r['accountingDocument'] or ""),
            isCancelled=str(r['billingDocumentIsCancelled'] or "False"),
            billingDate=str(r['billingDocumentDate'] or ""),
            entity="BillingDocument"
        )
    print(f"  Added {len(rows)} BillingDocument nodes")

def add_journal_entry_nodes(G, conn):
    # One accountingDocument can have multiple line items.
    # We group by accountingDocument to create one node per document.
    rows = conn.execute("""
        SELECT accountingDocument,
               SUM(amountInTransactionCurrency) as totalAmount,
               transactionCurrency,
               postingDate, referenceDocument, customer
        FROM journal_entry_items_accounts_receivable
        GROUP BY accountingDocument
    """).fetchall()

    for r in rows:
        node_id = f"JE_{r['accountingDocument']}"
        G.add_node(node_id,
            type="JournalEntry",
            label=f"JE {r['accountingDocument']}",
            accountingDocument=str(r['accountingDocument']),
            totalAmount=r['totalAmount'],
            currency=r['transactionCurrency'] or "INR",
            postingDate=str(r['postingDate'] or ""),
            referenceDocument=str(r['referenceDocument'] or ""),
            entity="JournalEntry"
        )
    print(f"  Added {len(rows)} JournalEntry nodes")

def add_payment_nodes(G, conn):
    # Group by accountingDocument same as journal entries
    rows = conn.execute("""
        SELECT accountingDocument,
               SUM(amountInTransactionCurrency) as totalAmount,
               transactionCurrency, postingDate, customer
        FROM payments_accounts_receivable
        GROUP BY accountingDocument
    """).fetchall()

    for r in rows:
        node_id = f"PAY_{r['accountingDocument']}"
        G.add_node(node_id,
            type="Payment",
            label=f"Payment {r['accountingDocument']}",
            accountingDocument=str(r['accountingDocument']),
            totalAmount=r['totalAmount'],
            currency=r['transactionCurrency'] or "INR",
            postingDate=str(r['postingDate'] or ""),
            entity="Payment"
        )
    print(f"  Added {len(rows)} Payment nodes")

# ── Edge builders ──────────────────────────────────────────────────────────

def add_customer_to_order_edges(G, conn):
    rows = conn.execute("""
        SELECT salesOrder, soldToParty FROM sales_order_headers
    """).fetchall()

    count = 0
    for r in rows:
        src = f"CUST_{r['soldToParty']}"
        tgt = f"SO_{r['salesOrder']}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, relation="placed")
            count += 1
    print(f"  Added {count} Customer→SalesOrder edges")

def add_order_to_product_edges(G, conn):
    rows = conn.execute("""
        SELECT DISTINCT salesOrder, material FROM sales_order_items
    """).fetchall()

    count = 0
    for r in rows:
        src = f"SO_{r['salesOrder']}"
        tgt = f"PROD_{r['material']}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, relation="contains")
            count += 1
    print(f"  Added {count} SalesOrder→Product edges")

def add_order_to_delivery_edges(G, conn):
    rows = conn.execute("""
        SELECT DISTINCT
            referenceSdDocument AS salesOrder,
            deliveryDocument
        FROM outbound_delivery_items
        WHERE referenceSdDocument IS NOT NULL
    """).fetchall()

    count = 0
    for r in rows:
        src = f"SO_{str(r['salesOrder']).strip()}"
        tgt = f"DEL_{str(r['deliveryDocument']).strip()}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, relation="fulfilled_by")
            count += 1
    print(f"  Added {count} SalesOrder→Delivery edges")

def add_delivery_to_billing_edges(G, conn):
    # billing_document_items.referenceSdDocument stores the DELIVERY document number
    # (807xxxxx range) — not the sales order number.
    # So we join billing_items directly to outbound_delivery_headers.
    rows = conn.execute("""
        SELECT DISTINCT
            bdi.referenceSdDocument AS deliveryDocument,
            bdi.billingDocument
        FROM billing_document_items bdi
        WHERE bdi.referenceSdDocument IS NOT NULL
    """).fetchall()

    count = 0
    for r in rows:
        src = f"DEL_{str(r['deliveryDocument']).strip()}"
        tgt = f"BILL_{str(r['billingDocument']).strip()}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, relation="billed_as")
            count += 1
    print(f"  Added {count} Delivery→BillingDocument edges")

def add_billing_to_journal_edges(G, conn):
    rows = conn.execute("""
        SELECT DISTINCT
            bdh.billingDocument,
            je.accountingDocument
        FROM billing_document_headers bdh
        JOIN journal_entry_items_accounts_receivable je
          ON je.referenceDocument = bdh.billingDocument
    """).fetchall()

    count = 0
    for r in rows:
        src = f"BILL_{r['billingDocument']}"
        tgt = f"JE_{r['accountingDocument']}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, relation="recorded_in")
            count += 1
    print(f"  Added {count} BillingDocument→JournalEntry edges")

def add_journal_to_payment_edges(G, conn):
    rows = conn.execute("""
        SELECT DISTINCT
            je.accountingDocument AS journalDoc,
            p.accountingDocument  AS paymentDoc
        FROM journal_entry_items_accounts_receivable je
        JOIN payments_accounts_receivable p
          ON p.clearingAccountingDocument = je.accountingDocument
    """).fetchall()

    count = 0
    for r in rows:
        src = f"JE_{r['journalDoc']}"
        tgt = f"PAY_{r['paymentDoc']}"
        if G.has_node(src) and G.has_node(tgt):
            G.add_edge(src, tgt, relation="cleared_by")
            count += 1
    print(f"  Added {count} JournalEntry→Payment edges")

# ── Main builder ───────────────────────────────────────────────────────────

def build_graph():
    print("\nBuilding graph...")
    G = nx.DiGraph()  # Directed graph — edges have direction (A → B)
    conn = get_connection()

    print("\n[Nodes]")
    add_customer_nodes(G, conn)
    add_sales_order_nodes(G, conn)
    add_product_nodes(G, conn)
    add_delivery_nodes(G, conn)
    add_billing_nodes(G, conn)
    add_journal_entry_nodes(G, conn)
    add_payment_nodes(G, conn)

    print("\n[Edges]")
    add_customer_to_order_edges(G, conn)
    add_order_to_product_edges(G, conn)
    add_order_to_delivery_edges(G, conn)
    add_delivery_to_billing_edges(G, conn)
    add_billing_to_journal_edges(G, conn)
    add_journal_to_payment_edges(G, conn)

    conn.close()

    print(f"\nGraph summary:")
    print(f"  Total nodes : {G.number_of_nodes()}")
    print(f"  Total edges : {G.number_of_edges()}")

    # Count by type
    type_counts = defaultdict(int)
    for _, data in G.nodes(data=True):
        type_counts[data.get('type', 'Unknown')] += 1
    for ntype, count in sorted(type_counts.items()):
        print(f"  {ntype:<20} {count} nodes")

    return G

# ── JSON exporter ──────────────────────────────────────────────────────────

def graph_to_json(G):
    """
    Converts the networkx graph into a JSON-serializable dict.
    The frontend expects exactly this format:
      { "nodes": [...], "edges": [...] }
    Each node has: id, type, label, plus all metadata fields.
    Each edge has: source, target, relation.
    """
    nodes = []
    for node_id, data in G.nodes(data=True):
        node = {"id": node_id}
        node.update(data)
        # Ensure all values are JSON-serializable (convert None, floats etc.)
        for k, v in node.items():
            if v is None:
                node[k] = ""
            elif isinstance(v, float):
                node[k] = round(v, 2)
        nodes.append(node)

    edges = []
    for src, tgt, data in G.edges(data=True):
        edges.append({
            "source": src,
            "target": tgt,
            "relation": data.get("relation", "")
        })

    return {"nodes": nodes, "edges": edges}

# ── Run directly to test ───────────────────────────────────────────────────

if __name__ == "__main__":
    G = build_graph()
    graph_json = graph_to_json(G)

    # Save to a file so we can inspect it
    output_path = "./graph_data.json"
    with open(output_path, "w") as f:
        json.dump(graph_json, f, indent=2)

    print(f"\nGraph JSON saved to: {output_path}")
    print(f"Sample node: {graph_json['nodes'][0]}")
    print(f"Sample edge: {graph_json['edges'][0]}")
    print("\nStep 3 complete.")