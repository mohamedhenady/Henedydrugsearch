import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd  # type: ignore
from rapidfuzz import fuzz, process  # type: ignore


def _new_cached_names():
    return {"en": [], "ar": [], "id": [], "strength": [], "forms": [], "alpha_tokens": []}


_CACHED_DB = None
_CACHED_NAMES = _new_cached_names()


def get_base_path():
    """Returns the base path for resources, compatible with scripts and EXEs."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DB_JSON = os.path.join(get_base_path(), "druglist.json")

STOP_WORDS = {
    "mg",
    "mcg",
    "ml",
    "gm",
    "g",
    "tab",
    "tabs",
    "tablet",
    "tablets",
    "caps",
    "cap",
    "capsule",
    "capsules",
    "vial",
    "amp",
    "ampoule",
    "susp",
    "suspension",
    "syrup",
    "syr",
    "eff",
    "sachets",
    "sachet",
    "granules",
    "eye",
    "drops",
    "drop",
    "ointment",
    "cream",
    "gel",
    "topical",
    "solution",
    "iv",
    "im",
    "inj",
    "injection",
    "fc",
    "fct",
    "f.c.",
    "s.r.",
    "retard",
    "forte",
    "extra",
    "plus",
}

DOSAGE_FORM_SYNONYMS = {
    "tablet": {"tab", "tabs", "tablet", "tablets"},
    "capsule": {"cap", "caps", "capsule", "capsules"},
    "syrup": {"syrup", "syr"},
    "suspension": {"susp", "suspension"},
    "injection": {"inj", "injection", "amp", "ampoule", "vial"},
    "cream": {"cream"},
    "ointment": {"ointment"},
    "gel": {"gel"},
    "drops": {"drop", "drops"},
    "spray": {"spray"},
    "solution": {"solution", "sol"},
    "powder": {"powder", "granules", "sachet", "sachets"},
}

ARABIC_CHAR_MAP = str.maketrans(
    {
        "\u0623": "\u0627",
        "\u0625": "\u0627",
        "\u0622": "\u0627",
        "\u0649": "\u064a",
        "\u0624": "\u0648",
        "\u0626": "\u064a",
        "\u0629": "\u0647",
        "\u0640": "",
        "\u0660": "0",
        "\u0661": "1",
        "\u0662": "2",
        "\u0663": "3",
        "\u0664": "4",
        "\u0665": "5",
        "\u0666": "6",
        "\u0667": "7",
        "\u0668": "8",
        "\u0669": "9",
    }
)
ARABIC_DIACRITICS_RE = re.compile(r"[\u0617-\u061A\u064B-\u0652]")
RATIO_RE = re.compile(r"\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)+")
VALUE_WITH_UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|gm|ml|iu|units?|%)\b", re.IGNORECASE)
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
ALPHA_TOKEN_RE = re.compile(r"[a-z\u0600-\u06FF]{3,}")
GENERIC_NAME_TOKENS = {"plus", "extra", "forte", "retard"}


def clear_cache():
    global _CACHED_DB, _CACHED_NAMES
    _CACHED_DB = None
    _CACHED_NAMES = _new_cached_names()


def is_arabic(text):
    if not text or pd.isna(text):
        return False
    return bool(re.search(r"[\u0600-\u06FF]", str(text)))


def _normalize_text(text):
    if not text or pd.isna(text):
        return ""
    normalized = str(text).lower().strip()
    normalized = ARABIC_DIACRITICS_RE.sub("", normalized)
    normalized = normalized.translate(ARABIC_CHAR_MAP)
    return normalized


def _normalize_number(value):
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value


def _dedupe_token_sequence(text):
    tokens = text.split()
    if not tokens:
        return ""
    seen = set()
    deduped = []
    for token in tokens:
        if token in seen:
            continue
        deduped.append(token)
        seen.add(token)
    return " ".join(deduped)


def clean_for_match(text):
    if not text or pd.isna(text):
        return ""

    normalized = _normalize_text(text)

    # Add spaces around alpha/number transitions.
    normalized = re.sub(r"(\d)([a-z\u0600-\u06FF])", r"\1 \2", normalized)
    normalized = re.sub(r"([a-z\u0600-\u06FF])(\d)", r"\1 \2", normalized)
    normalized = re.sub(r"\s*/\s*", "/", normalized)
    normalized = re.sub(r"[^a-z0-9\u0600-\u06FF\s/\.]", " ", normalized)

    words = [token.strip(".") for token in normalized.split()]
    words = [token for token in words if token]

    cleaned = [token for token in words if token not in STOP_WORDS]
    if cleaned:
        return " ".join(cleaned)
    return " ".join(words)


def _extract_strength_signature(text):
    signature = {"ratios": set(), "ratio_sets": set(), "values": set(), "numbers": set()}
    if not text or pd.isna(text):
        return signature

    normalized = _normalize_text(text)
    normalized = re.sub(r"[^a-z0-9\u0600-\u06FF\s/\.]", " ", normalized)

    for ratio in RATIO_RE.findall(normalized):
        parts = [_normalize_number(part) for part in re.split(r"\s*/\s*", ratio) if part]
        if len(parts) < 2:
            continue
        ratio_key = "/".join(parts)
        signature["ratios"].add(ratio_key)
        ratio_set_key = "/".join(sorted(parts, key=lambda value: float(value), reverse=True))
        signature["ratio_sets"].add(ratio_set_key)
        signature["numbers"].update(parts)

    for amount, unit in VALUE_WITH_UNIT_RE.findall(normalized):
        amount_norm = _normalize_number(amount)
        unit_norm = unit.lower()
        if unit_norm == "gm":
            unit_norm = "g"
        if unit_norm == "units":
            unit_norm = "unit"
        signature["values"].add(f"{amount_norm}{unit_norm}")
        signature["numbers"].add(amount_norm)

    for number in NUMBER_RE.findall(normalized):
        signature["numbers"].add(_normalize_number(number))

    return signature


def _extract_dosage_forms(text):
    forms = set()
    if not text or pd.isna(text):
        return forms

    normalized = _normalize_text(text)
    normalized = re.sub(r"[^a-z0-9\u0600-\u06FF\s]", " ", normalized)
    tokens = set(normalized.split())

    for form_name, aliases in DOSAGE_FORM_SYNONYMS.items():
        if aliases & tokens:
            forms.add(form_name)

    return forms


def _extract_alpha_tokens(text):
    if not text:
        return set()
    tokens = set(ALPHA_TOKEN_RE.findall(text.lower()))
    return {token for token in tokens if token not in GENERIC_NAME_TOKENS}


def _build_query_variants(raw_query):
    variants = []
    seen = set()

    if not raw_query:
        return variants

    raw_text = str(raw_query)
    text_without_parens = re.sub(r"\([^)]*\)", " ", raw_text)
    parenthetical_parts = re.findall(r"\(([^)]*)\)", raw_text)

    def add_variant(text, weight):
        cleaned = clean_for_match(text)
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        variants.append((cleaned, weight))

        deduped = _dedupe_token_sequence(cleaned)
        if deduped and deduped not in seen and deduped != cleaned:
            seen.add(deduped)
            variants.append((deduped, max(0.8, weight - 0.05)))

    # Prioritize outside-parentheses text because it is usually the main product phrase.
    add_variant(text_without_parens, 1.0)
    add_variant(raw_text, 0.92)

    for part in parenthetical_parts:
        add_variant(part, 0.82)

    return variants


def get_master_db(status_callback=None, force_reload=False):
    """Loads the database as a DataFrame directly from JSON."""
    global _CACHED_DB

    if force_reload:
        clear_cache()

    if _CACHED_DB is not None:
        return _CACHED_DB

    if status_callback:
        status_callback("Loading JSON database...")

    if not os.path.exists(DB_JSON):
        raise FileNotFoundError(f"Database file missing: {DB_JSON}")

    with open(DB_JSON, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        data_list = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else raw_data
        df = pd.DataFrame(data_list).reset_index(drop=True)

    _CACHED_DB = df
    return df


def get_search_names(status_callback=None, force_rebuild=False):
    """Builds cleaned names and lightweight matching metadata."""
    global _CACHED_NAMES

    if force_rebuild:
        _CACHED_NAMES = _new_cached_names()

    if _CACHED_NAMES["en"]:
        return _CACHED_NAMES

    df = get_master_db(status_callback)
    if status_callback:
        status_callback("Optimizing search index...")

    total = len(df)
    en_series = df.get("name_en", pd.Series([""] * total)).fillna("").astype(str)
    ar_series = df.get("name_ar", pd.Series([""] * total)).fillna("").astype(str)

    cached = _new_cached_names()
    for idx, (raw_en, raw_ar) in enumerate(zip(en_series, ar_series)):
        cached["en"].append(clean_for_match(raw_en))
        cached["ar"].append(clean_for_match(raw_ar))
        cached["id"].append(idx)

        combined_name = f"{raw_en} {raw_ar}"
        cached["strength"].append(_extract_strength_signature(combined_name))
        cached["forms"].append(_extract_dosage_forms(combined_name))
        cached["alpha_tokens"].append(_extract_alpha_tokens(clean_for_match(combined_name)))

    _CACHED_NAMES = cached
    return _CACHED_NAMES


def _strength_adjustment(query_sig, candidate_sig):
    adjustment = 0.0

    query_ratios = query_sig["ratios"]
    candidate_ratios = candidate_sig["ratios"]
    query_ratio_sets = query_sig["ratio_sets"]
    candidate_ratio_sets = candidate_sig["ratio_sets"]
    if query_ratios:
        if query_ratios & candidate_ratios:
            adjustment += 8.0
        elif query_ratio_sets and (query_ratio_sets & candidate_ratio_sets):
            adjustment += 6.0
        elif candidate_ratios:
            adjustment -= 10.0

    query_values = query_sig["values"]
    candidate_values = candidate_sig["values"]
    if query_values:
        overlap = len(query_values & candidate_values)
        if overlap:
            adjustment += min(6.0, overlap * 3.0)
        elif candidate_values:
            adjustment -= 5.0
    elif query_sig["numbers"]:
        overlap = len(query_sig["numbers"] & candidate_sig["numbers"])
        if overlap:
            adjustment += min(4.0, overlap * 1.5)
        elif candidate_sig["numbers"]:
            adjustment -= 2.5

    return adjustment


def _form_adjustment(query_forms, candidate_forms):
    if not query_forms:
        return 0.0
    if query_forms & candidate_forms:
        return 6.0
    if candidate_forms:
        return -4.0
    return 0.0


def _token_alignment_adjustment(query_tokens, candidate_tokens):
    if not query_tokens or not candidate_tokens:
        return 0.0

    similarities = []
    for query_token in query_tokens:
        best_similarity = max(fuzz.ratio(query_token, candidate_token) for candidate_token in candidate_tokens)
        similarities.append(best_similarity)

    strong_matches = sum(1 for score in similarities if score >= 80)
    exact_matches = sum(1 for score in similarities if score >= 95)
    avg_similarity = sum(similarities) / len(similarities)

    if strong_matches == 0:
        return -10.0

    bonus = min(10.0, (strong_matches * 3.0) + (exact_matches * 1.5))
    if avg_similarity < 65:
        bonus -= 2.5
    return bonus


def _rerank_score(
    query_clean,
    candidate_clean,
    pre_score,
    query_sig,
    candidate_sig,
    query_forms,
    candidate_forms,
    query_tokens,
    candidate_tokens,
):
    wr_score = fuzz.WRatio(query_clean, candidate_clean)
    set_score = fuzz.token_set_ratio(query_clean, candidate_clean)
    sort_score = fuzz.token_sort_ratio(query_clean, candidate_clean)

    base_score = (wr_score * 0.5) + (set_score * 0.3) + (sort_score * 0.2)
    score = (base_score * 0.9) + (pre_score * 0.1)
    score += _strength_adjustment(query_sig, candidate_sig)
    score += _form_adjustment(query_forms, candidate_forms)
    score += _token_alignment_adjustment(query_tokens, candidate_tokens)
    return max(0.0, min(100.0, score))


def _prefilter_candidates(query_variants, names_data, prefer_arabic, limit=40, score_cutoff=30):
    language_order = ["ar", "en"] if prefer_arabic else ["en", "ar"]
    best_by_idx = {}
    scorers = [(fuzz.WRatio, 1.0), (fuzz.token_set_ratio, 0.98)]

    for order_idx, lang in enumerate(language_order):
        lane_weight = 1.0 if order_idx == 0 else 0.97
        choices = names_data[lang]
        if not choices:
            continue

        for query_text, query_weight in query_variants:
            for scorer, scorer_weight in scorers:
                results = process.extract(
                    query_text,
                    choices,
                    scorer=scorer,
                    limit=limit,
                    score_cutoff=score_cutoff,
                )
                for candidate_text, score, idx in results:
                    weighted_score = score * lane_weight * query_weight * scorer_weight
                    prev = best_by_idx.get(idx)
                    if prev is None or weighted_score > prev[1]:
                        best_by_idx[idx] = (candidate_text, weighted_score)

    return [(idx, value[0], value[1]) for idx, value in best_by_idx.items()]


def _rank_candidates(raw_query, names_data, limit=50, min_score=45):
    query_variants = _build_query_variants(raw_query)
    if not query_variants:
        return []

    primary_query_clean = query_variants[0][0]
    prefer_arabic = is_arabic(raw_query)
    query_sig = _extract_strength_signature(raw_query)
    query_forms = _extract_dosage_forms(raw_query)
    query_tokens = _extract_alpha_tokens(primary_query_clean)

    prefilter_limit = max(90, limit * 8)
    candidate_pool = _prefilter_candidates(
        query_variants,
        names_data,
        prefer_arabic=prefer_arabic,
        limit=prefilter_limit,
        score_cutoff=30,
    )

    scored = []
    for idx, candidate_clean, pre_score in candidate_pool:
        if not candidate_clean:
            continue
        score = _rerank_score(
            primary_query_clean,
            candidate_clean,
            pre_score,
            query_sig,
            names_data["strength"][idx],
            query_forms,
            names_data["forms"][idx],
            query_tokens,
            names_data["alpha_tokens"][idx],
        )
        if score >= min_score:
            scored.append((idx, score))

    scored.sort(key=lambda item: item[1], reverse=True)
    return scored[:limit]


def _best_batch_match(raw_query, names_data, accept_score=50):
    ranked = _rank_candidates(raw_query, names_data, limit=1, min_score=40)
    if ranked and ranked[0][1] >= accept_score:
        return ranked[0]
    return None


def search_live(query, limit=50):
    """Search live against the cached JSON DataFrame."""
    if not query:
        return []

    try:
        names_data = get_search_names()
        db_df = get_master_db()
    except Exception as e:
        print(f"Search index error: {e}")
        return []

    ranked = _rank_candidates(query, names_data, limit=max(1, limit), min_score=45)
    matches = []
    for idx, score in ranked:
        row_pos = names_data["id"][idx]
        row = dict(db_df.iloc[row_pos])
        row["_score"] = round(score, 2)
        matches.append(row)
    return matches


def safe_read_csv(file_path, **kwargs):
    """Attempts to read a CSV or JSON file using multiple strategies."""
    path_str = str(file_path).lower()

    if path_str.endswith(".json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            data_list = raw_data.get("data", raw_data) if isinstance(raw_data, dict) else raw_data
            df = pd.DataFrame(data_list)
            if "nrows" in kwargs:
                df = df.head(kwargs["nrows"])
            return df
        except Exception as e:
            raise Exception(f"Failed to parse JSON file: {e}")

    encodings = ["utf-8", "utf-8-sig", "windows-1252", "latin1", "cp1256"]
    delimiters = [",", ";", "\t"]
    last_error = None

    for skip in range(51):
        for enc in encodings:
            test_kwargs = dict(kwargs)
            test_kwargs.pop("skiprows", None)
            test_kwargs["nrows"] = 20

            try:
                for sep in delimiters:
                    try:
                        df = pd.read_csv(file_path, encoding=enc, sep=sep, engine="c", skiprows=skip, **test_kwargs)
                        if not df.empty:
                            final_kwargs = dict(kwargs)
                            final_kwargs.pop("skiprows", None)
                            return pd.read_csv(
                                file_path,
                                encoding=enc,
                                sep=sep,
                                engine="c",
                                skiprows=skip,
                                **final_kwargs,
                            )
                    except Exception:
                        pass

                try:
                    df = pd.read_csv(file_path, encoding=enc, sep=None, engine="python", skiprows=skip, **test_kwargs)
                    if not df.empty:
                        final_kwargs = dict(kwargs)
                        final_kwargs.pop("skiprows", None)
                        return pd.read_csv(
                            file_path,
                            encoding=enc,
                            sep=None,
                            engine="python",
                            skiprows=skip,
                            **final_kwargs,
                        )
                except Exception:
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
    if path_str.endswith(".xlsx"):
        df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=0)
    else:
        df = safe_read_csv(file_path, nrows=0)
    return df.columns.tolist()


def get_excel_sheets(file_path):
    """Get list of sheet names from an Excel file."""
    try:
        xl_file = pd.ExcelFile(file_path)
        return xl_file.sheet_names
    except Exception:
        return []


def run_matching_v2(
    input_path,
    search_col,
    local_fields,
    db_fields,
    output_format="xlsx",
    sheet_name=0,
    progress_callback=None,
    status_callback=None,
):
    """Super-powered matching using in-memory JSON data."""
    try:
        names_data = get_search_names(status_callback)
        db_df = get_master_db()
    except Exception as e:
        raise Exception(f"Data Error: {str(e)}")

    if status_callback:
        status_callback("Reading input file...")

    is_xlsx = str(input_path).lower().endswith(".xlsx")
    if not is_xlsx and os.path.exists(input_path):
        try:
            with open(input_path, "rb") as f:
                if f.read(4) == b"\x50\x4b\x03\x04":
                    is_xlsx = True
        except Exception:
            pass

    if is_xlsx:
        input_df = pd.read_excel(input_path, sheet_name=sheet_name)
    else:
        input_df = safe_read_csv(input_path)

    input_df.columns = input_df.columns.str.strip()

    if input_df.empty:
        raise ValueError("Input file is empty!")

    if status_callback:
        status_callback("Matching items (JSON In-Memory Mode)...")

    matched_data = []
    total = len(input_df)
    query_cache: Dict[str, Optional[Tuple[int, float]]] = {}

    for i, (_, row) in enumerate(input_df.iterrows()):
        value = row.get(search_col, "")
        raw_query = "" if pd.isna(value) or str(value).lower() == "nan" else str(value).strip()
        query_clean = clean_for_match(raw_query)
        query_is_ar = is_arabic(raw_query)

        result_row = {}
        for field in local_fields:
            result_row[field] = row.get(field)

        result_row["search_query"] = raw_query
        result_row["match_found"] = "None"
        result_row["match_score"] = 0

        for field in db_fields:
            result_row[field] = None

        if query_clean:
            if query_clean not in query_cache:
                best = _best_batch_match(raw_query, names_data, accept_score=50)
                if best is None:
                    query_cache[query_clean] = None
                else:
                    best_idx, best_score = best
                    row_pos = names_data["id"][best_idx]
                    query_cache[query_clean] = (row_pos, round(best_score, 2))

            cached_match = query_cache.get(query_clean)
            if cached_match is not None:
                row_pos, best_score = cached_match
                db_row = db_df.iloc[row_pos]
                result_row["match_found"] = db_row.get("name_ar") if query_is_ar else db_row.get("name_en")
                result_row["match_score"] = best_score
                for field in db_fields:
                    result_row[field] = db_row.get(field)
            else:
                result_row["match_found"] = "No Match Found"
        else:
            result_row["match_found"] = "Empty Query"

        matched_data.append(result_row)
        if progress_callback:
            progress_callback(i + 1, total)

    if status_callback:
        status_callback("Saving results...")

    final_df = pd.DataFrame(matched_data)
    output_name = f"matched_output_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.{output_format}"
    output_path = os.path.join(os.path.dirname(input_path), output_name)

    if output_format == "xlsx":
        final_df.to_excel(output_path, index=False)
    else:
        final_df.to_json(output_path, orient="records", force_ascii=False, indent=2)

    return output_path, final_df
