import os
import json
import pandas as pd
from collections import defaultdict

DATASET_PATH = "./dataset"  # folder containing all 19 subfolders

def read_jsonl_folder(folder_path):
    """Read all .jsonl files in a folder and return as a DataFrame"""
    records = []
    for fname in os.listdir(folder_path):
        if fname.endswith(".jsonl") or fname.endswith(".jsonl"):
            fpath = os.path.join(folder_path, fname)
            with open(fpath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except:
                            pass
    return pd.DataFrame(records)

# ── Loop through every folder ──────────────────────────────────────────
results = {}

for entity_name in sorted(os.listdir(DATASET_PATH)):
    entity_path = os.path.join(DATASET_PATH, entity_name)
    if not os.path.isdir(entity_path):
        continue

    df = read_jsonl_folder(entity_path)
    results[entity_name] = df

    print(f"\n{'='*60}")
    print(f"ENTITY : {entity_name}")
    print(f"Rows   : {len(df)}")
    print(f"Columns: {list(df.columns)}")
    print("Sample :")
    print(df.head(2).to_string())

# ── Summary table ───────────────────────────────────────────────────────
print("\n\n" + "="*60)
print("SUMMARY")
print("="*60)
for name, df in results.items():
    print(f"{name:<45} {len(df):>6} rows   {len(df.columns):>3} cols")