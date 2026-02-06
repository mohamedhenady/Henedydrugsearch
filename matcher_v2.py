import pandas as pd
import json
import re
import os
import sys
from rapidfuzz import process, fuzz, utils

# Singleton for caching database
_CACHED_DB = None

def get_base_path():
    """Returns the base path for resources, compatible with scripts and EXEs."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

DB_FILE = os.path.join(get_base_path(), 'druglist.json')

STOP_WORDS = {
    'mg', 'mcg', 'ml', 'gm', 'g', 'tab', 'tabs', 'tablet', 'tablets', 'caps', 'cap', 'capsule', 
    'capsules', 'vial', 'amp', 'ampoule', 'susp', 'suspension', 'syrup', 'syr', 'eff', 'sachets', 
    'sachet', 'granules', 'eye', 'drops', 'drop', 'ointment', 'cream', 'gel', 'topical', 'solution',
    'iv', 'im', 'inj', 'injection', 'f.c.', 's.r.', 'retard', 'forte', 'extra', 'plus'
}

def is_arabic(text):
    if not text or pd.isna(text):
        return False
    return bool(re.search(r'[\u0600-\u06FF]', str(text)))

def clean_for_match(text):
    if not text or pd.isna(text): return ""
    text = str(text).lower()
    # Remove common punctuation but keep spaces
    text = re.sub(r'[^a-z0-9\u0600-\u06FF\s]', ' ', text)
    words = text.split()
    cleaned = [w for w in words if w not in STOP_WORDS and not re.match(r'^\d+$', w)]
    return " ".join(cleaned)

def get_master_db(status_callback=None):
    """Loads the druglist.json database (Cached)."""
    global _CACHED_DB
    if _CACHED_DB is not None:
        return _CACHED_DB

    if status_callback: status_callback("Reading database (JSON format)...")
    
    if not os.path.exists(DB_FILE):
        raise FileNotFoundError(f"Database file missing: {DB_FILE}")
    
    if os.path.getsize(DB_FILE) == 0:
        raise ValueError("Database file is empty!")

    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            obj = json.load(f)
        except json.JSONDecodeError:
            raise ValueError("Database file contains invalid JSON!")
            
    data = obj.get('data', [])
    if not data:
        raise ValueError("Database has no 'data' entries!")
        
    df = pd.DataFrame(data)
    
    # Pre-process for search once
    if 'name_en' not in df.columns: df['name_en'] = ""
    if 'name_ar' not in df.columns: df['name_ar'] = ""
    
    df['cleaned_en'] = df['name_en'].apply(clean_for_match)
    df['cleaned_ar'] = df['name_ar'].apply(clean_for_match)
    
    _CACHED_DB = df
    return df

def search_live(query, limit=50):
    """
    Search live against the cached DB.
    Returns a list of dicts with the top matches.
    """
    db = get_master_db()
    if not query:
        return []
        
    q_clean = clean_for_match(query)
    is_ar = is_arabic(q_clean)
    
    target_col = 'cleaned_ar' if is_ar else 'cleaned_en'
    choices = db[target_col].tolist()
    
    # Extract top N matches
    results = process.extract(
        q_clean,
        choices,
        scorer=fuzz.token_set_ratio,
        limit=limit,
        score_cutoff=50
    )
    
    # Map back to full rows
    matches = []
    for match in results:
        # match structure: (match_string, score, index)
        idx = match[2]
        row = db.iloc[idx].to_dict()
        row['_score'] = match[1] # Add score for reference
        matches.append(row)
        
    return matches

def get_file_headers(file_path):
    if file_path.endswith('.xlsx'):
        df = pd.read_excel(file_path, nrows=0)
    else:
        df = pd.read_csv(file_path, nrows=0)
    return df.columns.tolist()

def run_matching_v2(input_path, search_col, local_fields, db_fields, output_format='xlsx', progress_callback=None, status_callback=None):
    """
    Super-powered matching using pre-processing and rapidfuzz.
    """
    # 1. Load Master DB
    try:
        db_df = get_master_db(status_callback)
    except Exception as e:
        raise Exception(f"Database Error: {str(e)}")

    # 2. Load Input File
    if status_callback: status_callback("Reading input file...")
    if input_path.endswith('.xlsx'):
        input_df = pd.read_excel(input_path)
    else:
        input_df = pd.read_csv(input_path)

    if input_df.empty:
        raise ValueError("Input file is empty!")

    # 3. Optimize Search Index (Already done in get_master_db)
    if status_callback: status_callback("Preparing search index...")
    
    names_en_clean = db_df['cleaned_en'].tolist()
    names_ar_clean = db_df['cleaned_ar'].tolist()
    
    matched_data = []
    total = len(input_df)

    # 4. Process Loop
    if status_callback: status_callback("Matching items (Super-Powered Mode)...")
    
    for i, row in input_df.iterrows():
        raw_query = str(row.get(search_col, '')).strip()
        query = clean_for_match(raw_query)
        
        result_row = {field: row.get(field) for field in local_fields}
        result_row['search_query'] = raw_query

        if query:
            is_ar = is_arabic(raw_query)
            search_list = names_ar_clean if is_ar else names_en_clean
            
            match = process.extractOne(
                query, 
                search_list, 
                scorer=fuzz.token_set_ratio,
                score_cutoff=55
            )
            
            if match:
                score = match[1]
                idx = match[2]
                db_row = db_df.iloc[idx]
                
                result_row['match_found'] = db_row.get('name_en') if not is_ar else db_row.get('name_ar')
                result_row['match_score'] = round(score, 2)
                
                for field in db_fields:
                    result_row[field] = db_row.get(field)
            else:
                result_row['match_found'] = "No Match Found"
                result_row['match_score'] = 0
        else:
            result_row['match_found'] = "Empty Query"
            result_row['match_score'] = 0
            
        matched_data.append(result_row)
        if progress_callback:
            progress_callback(i + 1, total)

    # 5. Export
    if status_callback: status_callback("Saving results...")
    final_df = pd.DataFrame(matched_data)
    output_name = f"matched_output_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.{output_format}"
    output_path = os.path.join(os.path.dirname(input_path), output_name)

    if output_format == 'xlsx':
        final_df.to_excel(output_path, index=False)
    else:
        final_df.to_json(output_path, orient='records', force_ascii=False, indent=2)

    return output_path
