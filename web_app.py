import json
import os
import tempfile

import pandas as pd  # type: ignore
import streamlit as st  # type: ignore

import matcher_v2  # type: ignore


# Page Config
st.set_page_config(
    page_title="HenedyDrugSearch",
    page_icon="H",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling - Super Premium Theme
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Outfit:wght@300;500;800&display=swap');

    :root {
        --primary: #00d2ff;
        --secondary: #3a7bd5;
        --accent: #ff00c8;
        --bg-dark: #0a0c10;
        --glass: rgba(255, 255, 255, 0.05);
        --glass-border: rgba(255, 255, 255, 0.1);
    }

    .main {
        background: radial-gradient(circle at top right, #1a1c24, #0a0c10);
        font-family: 'Inter', sans-serif;
    }

    /* Glass Panels */
    .stSecondaryBlock {
        background: var(--glass) !important;
        backdrop-filter: blur(10px);
        border: 1px solid var(--glass-border);
        border-radius: 20px;
    }

    /* Titles */
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif;
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #111827 0%, #000000 100%);
        border-right: 1px solid var(--glass-border);
    }

    .developer-card {
        background: rgba(0, 210, 255, 0.1);
        border-left: 4px solid var(--primary);
        padding: 15px;
        border-radius: 10px;
        margin-top: 20px;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #00d2ff 0%, #3a7bd5 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        padding: 0.6rem 2rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(0, 210, 255, 0.3);
    }

    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0, 210, 255, 0.5);
        opacity: 0.9;
    }

    /* Inputs */
    .stTextInput>div>div>input, .stSelectbox>div>div>div {
        background-color: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 10px !important;
        color: white !important;
    }

    /* Dataframe Premium Border */
    .stDataFrame {
        border: 1px solid var(--glass-border);
        border-radius: 15px;
        overflow: hidden;
    }
</style>
""",
    unsafe_allow_html=True,
)


def _remove_temp_upload(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _get_temp_upload_path(uploaded_file):
    file_signature = (uploaded_file.name, uploaded_file.size)
    previous_signature = st.session_state.get("upload_signature")
    previous_path = st.session_state.get("upload_temp_path")

    if previous_signature != file_signature or not previous_path or not os.path.exists(previous_path):
        _remove_temp_upload(previous_path)
        suffix = os.path.splitext(uploaded_file.name)[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="henedy_upload_") as tmp_file:
            tmp_file.write(uploaded_file.getbuffer())
            new_path = tmp_file.name
        st.session_state["upload_signature"] = file_signature
        st.session_state["upload_temp_path"] = new_path

    return st.session_state.get("upload_temp_path")


# Sidebar
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3024/3024509.png", width=80)
st.sidebar.title("HenedyDrugSearch")

# Developer Label
st.sidebar.markdown(
    """
<div class="developer-card">
    <div style="font-size: 0.8rem; color: #aaa;">DEVELOPED BY</div>
    <div style="font-size: 1.1rem; font-weight: 800; color: #00d2ff;">Mohamed Henedy</div>
    <div style="font-size: 0.9rem; margin-top: 5px;">Tel: 01025272689</div>
</div>
""",
    unsafe_allow_html=True,
)

st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["File Wizard", "Manual Search"])


@st.cache_resource
def load_db():
    try:
        return matcher_v2.get_master_db()
    except Exception:
        return pd.DataFrame()


db_df = load_db()
if not db_df.empty:
    st.sidebar.success(f"Data Active: {len(db_df)} records")
else:
    st.sidebar.error("Database (druglist.json) missing")


# --- FILE WIZARD PAGE ---
if page == "File Wizard":
    st.markdown(
        """
        <div style="margin-bottom: 25px;">
            <h1 style="margin: 0; padding: 0;">HenedyDrugSearch Wizard</h1>
            <p style="color: #888; font-size: 1.1rem; margin-top: -5px;">Upload your Excel or CSV drug list and match it against the master database.</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    # Step 1: Upload
    with st.container():
        st.subheader("1. Source Selection")
        uploaded_file = st.file_uploader(
            "Upload Excel, CSV, or JSON",
            type=["xlsx", "csv", "json"],
            help="Select the file containing the drugs you want to match.",
        )

    if not uploaded_file:
        _remove_temp_upload(st.session_state.get("upload_temp_path"))
        st.session_state.pop("upload_signature", None)
        st.session_state.pop("upload_temp_path", None)

    if uploaded_file:
        temp_input_path = _get_temp_upload_path(uploaded_file)
        if not temp_input_path:
            st.error("Could not prepare uploaded file for processing.")
            st.stop()

        # For Excel files, show sheet selector.
        selected_sheet = 0
        is_excel = uploaded_file.name.lower().endswith(".xlsx")
        if is_excel:
            sheets = matcher_v2.get_excel_sheets(temp_input_path)
            if len(sheets) > 1:
                st.subheader("Select Excel Sheet")
                selected_sheet = st.selectbox("Choose the sheet to process:", sheets, help="Select the specific sheet from your Excel file")

        # Load Headers.
        try:
            if is_excel:
                df_preview = pd.read_excel(temp_input_path, sheet_name=selected_sheet, nrows=0)
            else:
                df_preview = matcher_v2.safe_read_csv(temp_input_path, nrows=0)

            df_preview.columns = df_preview.columns.str.strip()
            headers = df_preview.columns.tolist()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()

        st.markdown("---")
        # Step 2: Configure
        st.subheader("2. Configuration")
        col1, col2 = st.columns(2)

        best_col_idx = 0
        search_terms = ["drug", "name", "item", "product"]
        for i, header in enumerate(headers):
            if any(term in header.lower() for term in search_terms):
                best_col_idx = i
                break

        with col1:
            search_col = st.selectbox(
                "Target Column (Drug Name)",
                headers,
                index=best_col_idx,
                help="The column in your file that contains the drug names to search for.",
            )

            try:
                if is_excel:
                    df_col_preview = pd.read_excel(temp_input_path, sheet_name=selected_sheet, usecols=[search_col], nrows=5)
                else:
                    df_col_preview = matcher_v2.safe_read_csv(temp_input_path, usecols=[search_col], nrows=5)

                values = df_col_preview[search_col].astype(str).tolist()
                if values:
                    st.caption(f"Preview of '{search_col}': {', '.join(values[:5])}")
            except Exception:
                pass

        with col2:
            st.write("Output Format")
            out_fmt = st.radio("Format", ["xlsx", "json"], horizontal=True, label_visibility="collapsed")

        # Columns Selection
        st.markdown("#### Column Mapping")
        tabs = st.tabs(["Keep from Local File", "Add from Master DB"])

        with tabs[0]:
            local_cols = st.multiselect("Select columns to preserve", headers, default=headers)

        with tabs[1]:
            try:
                with open("config.json", "r", encoding="utf-8") as f_config:
                    config_data = json.load(f_config).get("fields", [])
                    db_keys = [field_info["key"] for field_info in config_data]
            except Exception:
                db_keys = db_df.columns.tolist() if not db_df.empty else []

            default_db = ["name_en", "price_retail", "price_wholesale", "barcode_primary"]
            default_db = [col for col in default_db if col in db_keys]
            db_cols = st.multiselect("Select columns to append", db_keys, default=default_db)

        st.markdown("---")
        # Step 3: Process
        st.subheader("3. Execution")
        if st.button("Start Matching Process"):
            msg_placeholder = st.empty()
            progress_bar = st.progress(0)

            def update_progress(curr, total):
                progress_bar.progress(curr / total)

            def update_status(msg):
                msg_placeholder.info(f"Status: {msg}")

            try:
                output_path, final_df = matcher_v2.run_matching_v2(
                    temp_input_path,
                    search_col,
                    local_cols,
                    db_cols,
                    out_fmt,
                    sheet_name=selected_sheet,
                    progress_callback=update_progress,
                    status_callback=update_status,
                )

                st.success("Processing complete. Previewing top rows below.")

                # --- RESULTS PREVIEW ---
                st.subheader("Results Preview (Top 50)")
                preview_cols = [col for col in (["search_query", "match_found", "match_score"] + db_cols) if col in final_df.columns]
                st.dataframe(final_df[preview_cols].head(50), use_container_width=True, hide_index=True)

                st.markdown("---")
                if os.path.exists(output_path):
                    with open(output_path, "rb") as f_out:
                        st.download_button(
                            label="Download Full Matched File",
                            data=f_out,
                            file_name=os.path.basename(output_path),
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            if out_fmt == "xlsx"
                            else "application/json",
                        )
                else:
                    st.warning("Output file was generated in memory but could not be found on disk.")
            except Exception as e:
                st.error(f"An error occurred during processing: {e}")


# --- MANUAL SEARCH PAGE ---
elif page == "Manual Search":
    st.markdown(
        """
        <div style="margin-bottom: 25px;">
            <h1 style="margin: 0; padding: 0;">Manual Database Search</h1>
            <p style="color: #888; font-size: 1.1rem; margin-top: -5px;">Browse the master database directly with real-time fuzzy matching.</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    query = st.text_input("Search Database", placeholder="Start typing drug name... (e.g. panadol)", label_visibility="collapsed")

    with st.expander("Display Settings"):
        if not db_df.empty:
            all_cols = db_df.columns.tolist()
        else:
            try:
                with open("config.json", "r", encoding="utf-8") as f_conf:
                    config_fields = json.load(f_conf).get("fields", [])
                    all_cols = [field_obj["key"] for field_obj in config_fields]
            except Exception:
                all_cols = []

        defaults = ["name_en", "price_retail", "price_wholesale", "barcode_primary", "manufacturer", "_score"]
        defaults = [col for col in defaults if col in all_cols or col == "_score"]
        show_cols = st.multiselect("Visible Columns", all_cols + ["_score"], default=defaults)

    if query:
        with st.spinner("Searching..."):
            results = matcher_v2.search_live(query, limit=50)

        if results:
            res_df = pd.DataFrame(results)
            valid_cols = [col for col in show_cols if col in res_df.columns]
            if not valid_cols:
                fallback_cols = [col for col in ["name_en", "name_ar", "_score"] if col in res_df.columns]
                valid_cols = fallback_cols if fallback_cols else res_df.columns.tolist()

            st.markdown(f"**Found {len(results)} matches:**")
            st.dataframe(res_df[valid_cols], use_container_width=True, hide_index=True)

            # Export helpers
            st.markdown("---")
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.subheader("Quick Copy for Excel")
                st.caption("Select below, copy (Ctrl+C), and paste directly into Excel.")
                tsv = res_df[valid_cols].to_csv(sep="\t", index=False)
                st.text_area("", value=tsv, height=150, label_visibility="collapsed")

            with col_b:
                st.subheader("Export Results")
                csv_data = res_df[valid_cols].to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    label="Download as CSV",
                    data=csv_data,
                    file_name="search_results.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        else:
            st.warning("No exact or partial matches found. Try refining your search query.")
