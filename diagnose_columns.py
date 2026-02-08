import pandas as pd
import matcher_v2

# Simulate what happens when the web app processes a file
print("=== DIAGNOSTIC: File Upload Column Matching ===\n")

# Create a test file similar to what users upload
test_file = "test_upload.xlsx"
test_data = pd.DataFrame({
    "Drug Name": ["Panadol", "Aspirin", "بنادول"],
    "Quantity": [10, 20, 15]
})
test_data.to_excel(test_file, index=False)
print(f"1. Created test file with columns: {list(test_data.columns)}")

# Read it back the way web_app.py does (preview for headers)
df_preview = pd.read_excel(test_file, nrows=0)
df_preview.columns = df_preview.columns.str.strip()
headers = df_preview.columns.tolist()
print(f"2. Web app sees headers: {headers}")

# User selects "Drug Name" as search column
search_col = "Drug Name"
print(f"3. User selects search column: '{search_col}'")

# Now when run_matching_v2 reads the FULL file
df_full = pd.read_excel(test_file)
df_full.columns = df_full.columns.str.strip()
print(f"4. Full file columns after strip: {list(df_full.columns)}")

# Test if column exists
print(f"5. Is '{search_col}' in columns? {search_col in df_full.columns}")

# Try to get data
for i, (idx, row) in enumerate(df_full.iterrows()):
    val = row.get(search_col, 'DEFAULT')
    print(f"   Row {i}: row.get('{search_col}') = '{val}'")

import os
os.remove(test_file)

print("\n=== DIAGNOSTIC COMPLETE ===")
