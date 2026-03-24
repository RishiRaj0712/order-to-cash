import os
import json
import sqlite3
import pandas as pd

DATASET_PATH = "./dataset"
DB_PATH = "./database.db"

# ── Helpers ────────────────────────────────────────────────────────────────

def flatten_value(val):
    """
    Some fields in the JSONL are nested dicts like:
    {'hours': 11, 'minutes': 31, 'seconds': 13}
    SQLite cannot store dicts, so we convert them to a readable string.
    Everything else is returned as-is.
    """
    if isinstance(val, dict):
        return str(val)
    return val

def read_jsonl_folder(folder_path):
    """
    Reads all .jsonl files inside a folder.
    Each line in a .jsonl file is one JSON record (one row of data).
    Returns a pandas DataFrame — think of it as an in-memory table.
    """
    records = []
    for fname in sorted(os.listdir(folder_path)):
        if fname.endswith(".jsonl"):
            fpath = os.path.join(folder_path, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass  # skip malformed lines
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)

def clean_dataframe(df):
    """
    Flattens any nested dict values in every cell.
    Also converts column names to lowercase for consistency.
    """
    for col in df.columns:
        df[col] = df[col].apply(flatten_value)
    return df

def infer_sqlite_type(series):
    """
    Looks at a pandas Series (one column) and decides whether
    it should be REAL (decimal number) or TEXT in SQLite.
    We keep it simple — only two types.
    """
    try:
        pd.to_numeric(series.dropna())
        return "REAL"
    except (ValueError, TypeError):
        return "TEXT"

# ── Main loader ────────────────────────────────────────────────────────────

def load_all_entities(conn):
    """
    Loops through every folder in the dataset directory.
    For each folder:
      1. Reads all .jsonl files into a DataFrame
      2. Cleans the data (flatten nested dicts)
      3. Creates a SQLite table with matching columns
      4. Inserts all rows
    """
    cursor = conn.cursor()
    summary = []

    for entity_name in sorted(os.listdir(DATASET_PATH)):
        entity_path = os.path.join(DATASET_PATH, entity_name)

        # Skip anything that isn't a folder
        if not os.path.isdir(entity_path):
            continue

        print(f"\nLoading: {entity_name}")

        # Step 1: Read JSONL files into DataFrame
        df = read_jsonl_folder(entity_path)
        if df.empty:
            print(f"  WARNING: No data found in {entity_name}, skipping.")
            continue

        # Step 2: Clean — flatten nested dicts, fix column names
        df = clean_dataframe(df)
        df.columns = [col.strip() for col in df.columns]

        # Step 3: Build CREATE TABLE statement dynamically
        # We look at each column and decide TEXT vs REAL
        col_defs = []
        for col in df.columns:
            col_type = infer_sqlite_type(df[col])
            # Wrap column names in quotes to handle special characters
            col_defs.append(f'"{col}" {col_type}')

        # Drop the table if it already exists (so re-running is safe)
        cursor.execute(f'DROP TABLE IF EXISTS "{entity_name}"')

        create_sql = f'CREATE TABLE "{entity_name}" ({", ".join(col_defs)})'
        cursor.execute(create_sql)

        # Step 4: Insert all rows
        # pandas .to_sql() handles this efficiently
        df.to_sql(entity_name, conn, if_exists="replace", index=False)

        row_count = len(df)
        col_count = len(df.columns)
        print(f"  OK — {row_count} rows, {col_count} columns")
        summary.append((entity_name, row_count, col_count))

    conn.commit()
    return summary

def verify_database(conn, summary):
    """
    After loading, reads back the row count from each table
    and confirms it matches what we inserted.
    Prints a clean summary table.
    """
    print("\n" + "="*60)
    print("DATABASE VERIFICATION")
    print("="*60)
    print(f"{'Entity':<45} {'Expected':>8} {'Actual':>8} {'Status':>8}")
    print("-"*60)

    all_ok = True
    cursor = conn.cursor()

    for entity_name, expected_rows, col_count in summary:
        cursor.execute(f'SELECT COUNT(*) FROM "{entity_name}"')
        actual_rows = cursor.fetchone()[0]
        status = "OK" if actual_rows == expected_rows else "MISMATCH"
        if status != "OK":
            all_ok = False
        print(f"{entity_name:<45} {expected_rows:>8} {actual_rows:>8} {status:>8}")

    print("-"*60)
    if all_ok:
        print("All tables loaded successfully.")
    else:
        print("WARNING: Some tables have row count mismatches.")
    print(f"\nDatabase saved to: {os.path.abspath(DB_PATH)}")

def print_schema(conn):
    """
    Prints the column names of every table.
    Useful to confirm the schema looks right before moving on.
    """
    print("\n" + "="*60)
    print("TABLE SCHEMAS")
    print("="*60)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        cursor.execute(f'PRAGMA table_info("{table}")')
        cols = [row[1] for row in cursor.fetchall()]
        print(f"\n{table}")
        print(f"  {', '.join(cols)}")

# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting database load...")
    print(f"Dataset path : {os.path.abspath(DATASET_PATH)}")
    print(f"Database path: {os.path.abspath(DB_PATH)}")

    # Connect to SQLite — creates the file if it doesn't exist
    conn = sqlite3.connect(DB_PATH)

    try:
        summary = load_all_entities(conn)
        verify_database(conn, summary)
        print_schema(conn)
    finally:
        conn.close()

    print("\nStep 2 complete. database.db is ready.")