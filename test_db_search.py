import pandas as pd
import json
from rapidfuzz import process, fuzz

with open('druglist.json', 'r', encoding='utf-8') as f:
    raw_data = json.load(f)
    data_list = raw_data.get('data', raw_data) if isinstance(raw_data, dict) else raw_data
    df = pd.DataFrame(data_list)

names_en = [str(n).lower() for n in df.get('name_en', [])]

queries = [
    "Concor 5mg (concor merik)",
    "Babay Aspirin (baby aspirin bay)",
    "paracetamol 500mg tab (Cetal)",
    "Targe 80",
    "Targe 160",
    "Co targe 160/12.5",
    "Co targe 80/12.5",
    "Blockatens 160/5",
    "Blockatens 160/10",
    "Vita Kids( total syrup )"
]

scorers = {
    "token_set_ratio": fuzz.token_set_ratio,
    "token_sort_ratio": fuzz.token_sort_ratio,
    "WRatio": fuzz.WRatio,
    "QRatio": fuzz.QRatio,
}

for q in queries:
    print(f"--- QUERY: {q} ---")
    for name, scorer in scorers.items():
        matches = process.extract(q.lower(), names_en, scorer=scorer, limit=3)
        print(f"{name}:")
        for m in matches:
            print(f"  {m[1]:.2f} - {m[0]}")
    print()
