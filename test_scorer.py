from rapidfuzz import fuzz

queries = [
    "Concor 5mg (concor merik)",
    "Babay Aspirin (baby aspirin bay)",
    "paracetamol 500mg tab (Cetal)",
    "Targe 80",
    "Co targe 160/12.5"
]

targets = [
    "5fu 250mg/5ml vial",
    "4 wet intimate gel 100 ml",
    "abimol 500 mg 20 tab.",
    "acnesept 80 gram soap",
    "5-fluorouracil-ebewe 250mg/5ml i.v. vial"
]

scorers = {
    "WRatio": fuzz.WRatio,
    "token_set_ratio": fuzz.token_set_ratio,
    "token_sort_ratio": fuzz.token_sort_ratio,
    "QRatio": fuzz.QRatio,
    "partial_ratio": fuzz.partial_ratio
}

for q, t in zip(queries, targets):
    print(f"Query: {q}")
    print(f"Target: {t}")
    for name, scorer in scorers.items():
        print(f"  {name}: {scorer(q, t)}")
    print("-" * 20)
