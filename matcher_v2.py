import pandas as pd # type: ignore
import json
import re
import os
import sys
from rapidfuzz import process, fuzz, utils # type: ignore

# Singleton for caching database
_CACHED_DB = None
_CACHED_NAMES = {"en": [], "ar": [], "id": []}

def get_base_path():
    """Returns the base path for resources, compatible with scripts and EXEs."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

DB_JSON = os.path.join(get_base_path(), 'druglist.json')

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
    text = re.sub(r'[^a-z0-9\u0600-\u06FF\s]', ' ', text)
    words = text.split()
    cleaned = [w for w in words if w not in STOP_WORDS]
    if not cleaned and words:
        return " ".join(words)
    return " ".join(cleaned)

def get_master_db(status_callback=None):
    """Loads the database as a DataFrame directly from JSON."""
    global _CACHED_DB
    if _CACHED_DB is not None:
        return _CACHED_DB

    if status_callback: status_callback("Loading JSON database...")
    
    if not os.path.exists(DB_JSON):
        raise FileNotFoundError(f"Database file missing: {DB_JSON}")
    
    with open(DB_JSON, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        data_list = raw_data.get('data', raw_data) if isinstance(raw_data, dict) else raw_data
        df = pd.DataFrame(data_list)
    
    _CACHED_DB = df
    return df

def get_search_names(status_callback=None):
    """Retrieves cleaned names for fuzzy matching (In-Memory)."""
    global _CACHED_NAMES
    if _CACHED_NAMES["en"]:
        return _CACHED_NAMES
        
    df = get_master_db(status_callback)
    if status_callback: status_callback("Optimizing search index...")
    
    _CACHED_NAMES["en"] = [clean_for_match(str(n)) for n in df.get('name_en', [])]
    _CACHED_NAMES["ar"] = [clean_for_match(str(n)) for n in df.get('name_ar', [])]
    # In JSON mode, ID is just the dataframe index
    _CACHED_NAMES["id"] = list(df.index)
    return _CACHED_NAMES

def search_live(query, limit=50):
    """
    Search live against the cached JSON DataFrame.
    """
    if not query:
        return []
    
    try:
        names_data = get_search_names()
        db_df = get_master_db()
    except Exception as e:
        print(f"Search index error: {e}")
        return []
        
    q_clean = clean_for_match(query)
    is_ar = is_arabic(query)
    
    choices = names_data['ar'] if is_ar else names_data['en']
    
    results = process.extract(
        q_clean,
        choices,
        scorer=fuzz.token_set_ratio,
        limit=limit,
        score_cutoff=50
    )
    
    matches = []
    for match in results:
        idx = match[2]
        row_id = names_data['id'][idx]
        row = dict(db_df.iloc[row_id])
        row['_score'] = match[1]
        matches.append(row)
        
    return matches

def safe_read_csv(file_path, **kwargs):
    """Attempts to read a CSV or JSON file using multiple strategies."""
    path_str = str(file_path).lower()
    
    # --- JSON SUPPORT ---
    if path_str.endswith('.json'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
            data_list = raw_data.get('data', raw_data) if isinstance(raw_data, dict) else raw_data
            df = pd.DataFrame(data_list)
            if 'nrows' in kwargs:
                df = df.head(kwargs['nrows'])
            return df
        except Exception as e:
            raise Exception(f"Failed to parse JSON file: {e}")

    # --- CSV SUPPORT (with Deep-Dive skip-row recovery) ---
    encodings = ['utf-8', 'utf-8-sig', 'windows-1252', 'latin1', 'cp1256']
    delimiters = [',', ';', '\t']
    last_error = None
    
    for skip in range(51):
        for enc in encodings:
            test_kwargs = dict(kwargs)
            test_kwargs.pop('skiprows', None)
            test_kwargs['nrows'] = 20 
            
            try:
                # 1. Try Explicit Delimiters First (More reliable than sniffer)
                for sep in delimiters:
                    try:
                        df = pd.read_csv(file_path, encoding=enc, sep=sep, engine='c', skiprows=skip, **test_kwargs)
                        if not df.empty:
                            final_kwargs = dict(kwargs)
                            final_kwargs.pop('skiprows', None)
                            return pd.read_csv(file_path, encoding=enc, sep=sep, engine='c', skiprows=skip, **final_kwargs)
                    except:
                        pass

                # 2. Try Sniffer as Fallback
                try:
                    df = pd.read_csv(file_path, encoding=enc, sep=None, engine='python', skiprows=skip, **test_kwargs)
                    if not df.empty:
                        final_kwargs = dict(kwargs)
                        final_kwargs.pop('skiprows', None)
                        return pd.read_csv(file_path, encoding=enc, sep=None, engine='python', skiprows=skip, **final_kwargs)
                except:
                    pass

            except Exception as e:
                last_error = e
            
    if isinstance(last_error, Exception):
        raise last_error
    raise Exception(f"Failed to read CSV after multiple attempts including skipping up to 50 metadata rows: {file_path}")

def get_file_headers(file_path, sheet_name=0):
    """Get column headers from a file.
    
    Args:
        sheet_name: For Excel files, the sheet name or index (default: 0)
    """
    path_str = str(file_path).lower()
    if path_str.endswith('.xlsx'):
        df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0)
    else:
        df = safe_read_csv(file_path, nrows=0)
    return df.columns.tolist()

def get_excel_sheets(file_path):
    """Get list of sheet names from an Excel file."""
    try:
        xl_file = pd.ExcelFile(file_path)
        return xl_file.sheet_names
    except:
        return []

def run_matching_v2(input_path, search_col, local_fields, db_fields, output_format='xlsx', sheet_name=0, progress_callback=None, status_callback=None):
    """
    Super-powered matching using in-memory JSON data.
    
    Args:
        sheet_name: For Excel files, the sheet name or index (default: 0)
    """
    # 1. Load Data
    try:
        names_data = get_search_names(status_callback)
        db_df = get_master_db()
    except Exception as e:
        raise Exception(f"Data Error: {str(e)}")

    # 2. Load Input
    if status_callback: status_callback("Reading input file...")
    if str(input_path).lower().endswith('.xlsx'):
        input_df = pd.read_excel(input_path, sheet_name=sheet_name)
    else:
        input_df = safe_read_csv(input_path)

    # Normalize column names (strip whitespace)
    input_df.columns = input_df.columns.str.strip()

    if input_df.empty:
        raise ValueError("Input file is empty!")

    # 3. Process
    if status_callback: status_callback("Matching items (JSON In-Memory Mode)...")
    
    matched_data = []
    total = len(input_df)
    
    for i, (index, row) in enumerate(input_df.iterrows()):
        raw_query = str(row.get(search_col, '')).strip()
        query = clean_for_match(raw_query)
        
        # Use dict() to prevent the IDE from narrowing the type based on local_fields
        result_row = dict({field: row.get(field) for field in local_fields})
        result_row['search_query'] = raw_query

        if query:
            is_ar = is_arabic(raw_query)
            search_list = names_data['ar'] if is_ar else names_data['en']
            
            match = process.extractOne(query, search_list, scorer=fuzz.token_set_ratio, score_cutoff=55)
            
            if match:
                score = match[1]
                idx = match[2]
                db_row = db_df.iloc[idx]
                
                result_row['match_found'] = db_row['name_en'] if not is_ar else db_row['name_ar']
                result_row['match_score'] = round(score, 2)
                for field in db_fields:
                    result_row[field] = db_row.get(field)
            else:
                # Fallback
                match = process.extractOne(raw_query.lower(), search_list, scorer=fuzz.token_set_ratio, score_cutoff=40)
                if match:
                    idx = match[2]
                    db_row = db_df.iloc[idx]
                    result_row['match_found'] = db_row['name_en'] if not is_ar else db_row['name_ar']
                    result_row['match_score'] = round(match[1], 2)
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

    return output_path, final_df
