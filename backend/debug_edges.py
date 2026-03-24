import sqlite3

conn = sqlite3.connect("./database.db")
conn.row_factory = sqlite3.Row

print("=== Sample from outbound_delivery_items ===")
rows = conn.execute("""
    SELECT deliveryDocument, referenceSdDocument
    FROM outbound_delivery_items
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  deliveryDoc: '{r['deliveryDocument']}'  referenceSdDoc: '{r['referenceSdDocument']}'  type: {type(r['referenceSdDocument'])}")

print("\n=== Sample from billing_document_items ===")
rows = conn.execute("""
    SELECT billingDocument, referenceSdDocument
    FROM billing_document_items
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  billingDoc: '{r['billingDocument']}'  referenceSdDoc: '{r['referenceSdDocument']}'  type: {type(r['referenceSdDocument'])}")

print("\n=== Sales orders we know exist in sales_order_headers ===")
rows = conn.execute("""
    SELECT salesOrder FROM sales_order_headers LIMIT 10
""").fetchall()
for r in rows:
    print(f"  salesOrder: '{r['salesOrder']}'  type: {type(r['salesOrder'])}")

print("\n=== Do ANY delivery referenceSdDocument values match sales orders? ===")
result = conn.execute("""
    SELECT COUNT(*) as cnt
    FROM outbound_delivery_items odi
    JOIN sales_order_headers soh
      ON CAST(odi.referenceSdDocument AS TEXT) = CAST(soh.salesOrder AS TEXT)
""").fetchone()
print(f"  Matches: {result['cnt']}")

print("\n=== Do ANY billing referenceSdDocument values match sales orders? ===")
result = conn.execute("""
    SELECT COUNT(*) as cnt
    FROM billing_document_items bdi
    JOIN sales_order_headers soh
      ON CAST(bdi.referenceSdDocument AS TEXT) = CAST(soh.salesOrder AS TEXT)
""").fetchone()
print(f"  Matches: {result['cnt']}")

print("\n=== Unique referenceSdDocument values in delivery_items (first 10) ===")
rows = conn.execute("""
    SELECT DISTINCT referenceSdDocument 
    FROM outbound_delivery_items 
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  '{r['referenceSdDocument']}'")

print("\n=== Unique referenceSdDocument values in billing_items (first 10) ===")
rows = conn.execute("""
    SELECT DISTINCT referenceSdDocument 
    FROM billing_document_items 
    LIMIT 10
""").fetchall()
for r in rows:
    print(f"  '{r['referenceSdDocument']}'")

conn.close()