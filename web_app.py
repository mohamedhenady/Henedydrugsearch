import streamlit as st # type: ignore
import pandas as pd # type: ignore
import matcher_v2 # type: ignore
import os
import json

# Page Config
st.set_page_config(
    page_title="Drug Matched Pro",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #1f6aa5;
        color: white;
        font-weight: bold;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #2980b9;
        border: none;
        transform: translateY(-2px);
    }
    .stTextInput>div>div>input {
        background-color: #1a1c24;
        color: #ffffff;
    }
    .stDataFrame {
        border: 1px solid #1f6aa5;
        border-radius: 10px;
    }
    h1 {
        color: #1f6aa5;
        font-weight: 800 !important;
    }
    .sidebar .sidebar-content {
        background-image: linear-gradient(#2e3b4e,#2e3b4e);
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3024/3024509.png", width=100)
st.sidebar.title("DrugMatch Pro")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["📂 File Wizard", "🔍 Manual Search"])

@st.cache_resource
def load_db():
    try:
        # We try to load a small sample or check if it exists
        return matcher_v2.get_master_db()
    except:
        return pd.DataFrame()

db_df = load_db()
if not db_df.empty:
    st.sidebar.success(f"✅ Data Active: {len(db_df)} records")
else:
    st.sidebar.error("⚠️ Database (druglist.json) missing!")

# --- FILE WIZARD PAGE ---
if page == "📂 File Wizard":
    st.markdown("# 📂 File Matching Wizard")
    st.info("Upload your Excel or CSV drug list and match it against the Master Database.")
    
    # Step 1: Upload
    with st.container():
        st.subheader("1. Source Selection")
        uploaded_file = st.file_uploader("Upload Excel, CSV, or JSON", type=['xlsx', 'csv', 'json'], help="Select the file containing the drugs you want to match.")
    
    if uploaded_file:
        # Save temp file for processing (matcher_v2 expects path)
        with open("temp_input", "wb") as f_in:
            f_in.write(uploaded_file.getbuffer())
        
        # For Excel files, show sheet selector
        selected_sheet = 0
        if uploaded_file.name.endswith('.xlsx'):
            sheets = matcher_v2.get_excel_sheets("temp_input")
            if len(sheets) > 1:
                st.subheader("📑 Select Excel Sheet")
                selected_sheet = st.selectbox("Choose the sheet to process:", sheets, help="Select the specific sheet from your Excel file")
        
        # Load Headers
        try:
            if uploaded_file.name.endswith('.xlsx'):
                df_preview = pd.read_excel("temp_input", sheet_name=selected_sheet, nrows=0)
            else:
                # Use robust reader for CSV preview too
                df_preview = matcher_v2.safe_read_csv("temp_input", nrows=0)
            
            # Normalize column names (strip whitespace)
            df_preview.columns = df_preview.columns.str.strip()
            headers = df_preview.columns.tolist()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()
        
        st.markdown("---")
        # Step 2: Configure
        st.subheader("2. Configuration")
        col1, col2 = st.columns(2)
        # Try to guess the best column
        best_col_idx = 0
        search_terms = ['الصنف', 'drug', 'name', 'item', 'product', 'البند', 'الاسم']
        for i, h in enumerate(headers):
            if any(term in h.lower() for term in search_terms):
                best_col_idx = i
                break

        with col1:
            search_col = st.selectbox("🎯 Target Column (Drug Name)", headers, index=best_col_idx, help="The column in your file that contains the drug names to search for.")
            
            # Show a small preview of the selected column to help the user
            try:
                if uploaded_file.name.endswith('.xlsx'):
                    df_col_preview = pd.read_excel("temp_input", sheet_name=selected_sheet, usecols=[search_col], nrows=5)
                else:
                    df_col_preview = matcher_v2.safe_read_csv("temp_input", usecols=[search_col], nrows=5)
                
                st.caption(f"Preview of '{search_col}': {', '.join(df_col_preview[search_col].astype(str).tolist())}...")
            except:
                pass
            
        with col2:
            st.write("📦 Output Format")
            out_fmt = st.radio("Format", ["xlsx", "json"], horizontal=True, label_visibility="collapsed")

        # Columns Selection
        st.markdown("#### 🛠️ Column Mapping")
        tabs = st.tabs(["📄 Keep from Local File", "🏦 Add from Master DB"])
        
        with tabs[0]:
            local_cols = st.multiselect("Select columns to preserve", headers, default=headers)
            
        with tabs[1]:
            try:
                with open('config.json', 'r', encoding='utf-8') as f_config:
                    config_data = json.load(f_config).get('fields', [])
                    db_keys = [field_info['key'] for field_info in config_data]
            except:
                db_keys = db_df.columns.tolist() if not db_df.empty else []
                
            default_db = ['name_en', 'price_retail', 'price_wholesale', 'barcode_primary']
            default_db = [c for c in default_db if c in db_keys]
            
            db_cols = st.multiselect("Select columns to append", db_keys, default=default_db)
            
        st.markdown("---")
        # Step 3: Process
        st.subheader("3. Execution")
        if st.button("🚀 Start Matching Process"):
            msg_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            def update_progress(curr, total):
                progress_bar.progress(curr / total)
            
            def update_status(msg):
                msg_placeholder.info(f"Status: {msg}")
                
            try:
                output_path, final_df = matcher_v2.run_matching_v2(
                    "temp_input",
                     search_col,
                     local_cols,
                     db_cols,
                     out_fmt,
                     sheet_name=selected_sheet,
                     progress_callback=update_progress,
                     status_callback=update_status
                )
                
                st.balloons()
                st.success("✨ Processing Complete! Previewing top results below.")
                
                # --- RESULTS PREVIEW ---
                st.subheader("📋 Results Preview (Top 50)")
                # Highlight scores and matches
                preview_cols = ['search_query', 'match_found', 'match_score'] + db_cols
                st.dataframe(
                    final_df[preview_cols].head(50), 
                    use_container_width=True,
                    hide_index=True
                )

                st.markdown("---")
                # Read output back to simplify download
                with open(output_path, "rb") as f_out:
                    st.download_button(
                        label="⬇️ Download Full Matched File",
                        data=f_out,
                        file_name=os.path.basename(output_path),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if out_fmt == "xlsx" else "application/json"
                    )
            except Exception as e:
                st.error(f"❌ An error occurred during processing: {e}")

# --- MANUAL SEARCH PAGE ---
elif page == "🔍 Manual Search":
    st.markdown("# 🔍 Manual Database Search")
    st.write("Browse the Master Database directly with real-time fuzzy matching.")
    
    query = st.text_input("Search Database", placeholder="Start typing drug name... (e.g. panadol)", label_visibility="collapsed")
    
    # Columns Selector
    with st.expander("🛠️ Display Settings"):
        if not db_df.empty:
            all_cols = db_df.columns.tolist()
        else:
            try:
                with open('config.json', 'r', encoding='utf-8') as f_conf:
                    config_fields = json.load(f_conf).get('fields', [])
                    all_cols = [field_obj['key'] for field_obj in config_fields]
            except:
                all_cols = []
                
        defaults = ['name_en', 'price_retail', 'price_wholesale', 'barcode_primary', 'manufacturer']
        defaults = [c for c in defaults if c in all_cols]
        show_cols = st.multiselect("Visible Columns", all_cols, default=defaults)
    
    if query:
        with st.spinner("Searching..."):
            results = matcher_v2.search_live(query, limit=50)
        
        if results:
            res_df = pd.DataFrame(results)
            # Filter cols
            valid_cols = [c for c in show_cols if c in res_df.columns]
            
            st.markdown(f"**Found {len(results)} matches:**")
            st.dataframe(res_df[valid_cols], use_container_width=True, hide_index=True)
            
            # Export Helpers
            st.markdown("---")
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.subheader("📋 Quick Copy for Excel")
                st.caption("Select below, copy (Ctrl+C), and paste directly into Excel.")
                tsv = res_df[valid_cols].to_csv(sep="\t", index=False)
                st.text_area("", value=tsv, height=150, label_visibility="collapsed")
            
            with col_b:
                st.subheader("💾 Export Results")
                csv_data = res_df[valid_cols].to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="Download as CSV",
                    data=csv_data,
                    file_name="search_results.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.warning("😕 No exact or partial matches found. Try refining your search query.")
