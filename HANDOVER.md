# Project Handover Document: Drug Wizard Pro

**Date:** 2026-02-06
**Status:** Feature Complete (Desktop & Web)

## Project Overview
This tool allows users to map drug lists (`.xlsx`/`.csv`) against a **Master Drug Database** using fuzzy matching algorithms. It supports:
1.  **File Wizard**: Matching uploaded files with custom columns.
2.  **Manual Search**: Live searching the master database.
3.  **Data Export**: Copy-paste to Excel or download matched files.

## Key Files
| File | Purpose |
| :--- | :--- |
| `web_app.py` | **[NEW]** Streamlit Web Application (for online use). |
| `drug_wizard.py` | Desktop GUI Application (CustomTkinter). |
| `matcher_v2.py` | Core backend logic (search, fuzzy matching, DB caching). |
| `druglist.json` | The Master Database (Recovered & Fixed). |
| `config.json` | Configuration for database schema (columns/keys). |
| `fix_json_db.py` | *Utility Script* used to regenerate JSON from CSV (archived). |
| `requirements.txt` | Python dependencies for deployment. |

## Current State
1.  **Database Fixed**: The `druglist.json` was corrupted (`NaN` values) and missing keys. It has been regenerated from `druglist.csv` to match `config.json` exactly.
2.  **Manual Search Added**: Both Desktop and Web apps now support live searching with column selection.
3.  **Web Ready**: A `web_app.py` exists, fully replicating the desktop features for browser use.
4.  **Git Initialized**: A local git repo is active with the initial commit.

---

## How to Run (New PC)

### 1. Setup Environment
Install the dependencies using the provided file:
```bash
pip install -r requirements.txt
```

### 2. Run Web Version (Recommended)
This runs the app in your local browser.
```bash
streamlit run web_app.py
```

### 3. Run Desktop Version
This runs the Windows GUI executable style app.
```bash
python drug_wizard.py
```

### 4. Deploy Online (Free)
1.  Push this folder to a **GitHub Repository**.
2.  Go to [share.streamlit.io](https://share.streamlit.io/).
3.  Connect to your repo -> Main file: `web_app.py`.
4.  Click **Deploy**.

## AI Context for Next Agent
- **Database**: `druglist.json` is the source of truth. It is loaded via `matcher_v2.get_master_db()` which uses a singleton pattern for caching.
- **Search Logic**: Uses `rapidfuzz` in `matcher_v2.search_live()`. It handles English/Arabic detection automatically.
- **UI Frameworks**: The project supports **two** frontends: `Streamlit` (Web) and `CustomTkinter` (Desktop). Any logic changes to `matcher_v2.py` automatically update both.

## Outstanding Items / Notes
- The `druglist.csv` (source) had no headers; mapping was inferred and hardcoded in the `fix_json_db.py` script.
- `druglist.json` is large (~18MB). Loading takes ~1-2 seconds initially.
