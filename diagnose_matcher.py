import matcher_v2
import pandas as pd
import os

# Create a single-column CSV
test_csv = "diag_input.csv"
pd.DataFrame({"drug": ["Panadol", "بنادول"]}).to_csv(test_csv, index=False)

print("--- DIAGNOSTIC START ---")
try:
    print(f"Reading {test_csv} with safe_read_csv...")
    df = matcher_v2.safe_read_csv(test_csv)
    print("DataFrame Columns:", df.columns.tolist())
    print("DataFrame Values:\n", df)
    
    search_col = "drug"
    for i, (idx, row) in enumerate(df.iterrows()):
        val = row.get(search_col)
        print(f"Row {i} - Column '{search_col}': '{val}' (Type: {type(val)})")

except Exception as e:
    print(f"ERROR in safe_read_csv: {e}")

# Clean up
if os.path.exists(test_csv): os.remove(test_csv)
print("--- DIAGNOSTIC END ---")
