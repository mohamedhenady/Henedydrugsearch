import streamlit as st
import pandas as pd
import matcher_v2
import os
import json

# Page Config
st.set_page_config(page_title="Drug Matched Pro", layout="wide")

# Sidebar
st.sidebar.title("DrugMatch Pro")
page = st.sidebar.radio("Navigation", ["File Wizard", "Manual Search"])

@st.cache_resource
def load_db():
    return matcher_v2.get_master_db()

try:
    db_df = load_db()
    st.sidebar.success(f"Database Loaded: {len(db_df)} records")
except Exception as e:
    st.sidebar.error(f"DB Error: {e}")
    st.stop()

# --- FILE WIZARD PAGE ---
if page == "File Wizard":
    st.title("📂 File Matching Wizard")
    
    # Step 1: Upload
    uploaded_file = st.file_uploader("Upload Excel or CSV", type=['xlsx', 'csv'])
    
    if uploaded_file:
        # Save temp file for processing (matcher_v2 expects path)
        with open("temp_input", "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Load Headers
        if uploaded_file.name.endswith('.xlsx'):
            df_preview = pd.read_excel(uploaded_file, nrows=0)
        else:
            df_preview = pd.read_csv(uploaded_file, nrows=0)
        
        headers = df_preview.columns.tolist()
        
        # Step 2: Configure
        col1, col2 = st.columns(2)
        with col1:
            search_col = st.selectbox("Select Drug Name Column", headers)
            
        with col2:
            st.write("Output Format")
            out_fmt = st.radio("Format", ["xlsx", "json"], horizontal=True)

        # Columns Selection
        st.subheader("Select Columns to Export")
        tabs = st.tabs(["Local File Columns", "Database Columns"])
        
        with tabs[0]:
            local_cols = st.multiselect("Keep from Input File", headers, default=headers)
            
        with tabs[1]:
            # Load config for labels if available
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f).get('fields', [])
                    db_keys = [f['key'] for f in config]
            except:
                db_keys = db_df.columns.tolist()
                
            default_db = ['name_en', 'price_retail', 'price_wholesale', 'barcode_primary']
            default_db = [c for c in default_db if c in db_keys]
            
            db_cols = st.multiselect("Add from Master DB", db_keys, default=default_db)
            
        # Step 3: Process
        if st.button("🚀 Start Matching"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(curr, total):
                progress_bar.progress(curr / total)
            
            def update_status(msg):
                status_text.text(msg)
                
            output_path = matcher_v2.run_matching_v2(
                "temp_input", # This would need to be a real path, simplified here
                 search_col,
                 local_cols,
                 db_cols,
                 out_fmt,
                 progress_callback=update_progress,
                 status_callback=update_status
            )
            
            # Read output back to simplify download
            with open(output_path, "rb") as f:
                btn = st.download_button(
                    label="Download Result",
                    data=f,
                    file_name=os.path.basename(output_path),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if out_fmt == "xlsx" else "application/json"
                )
            st.success("Processing Complete!")

# --- MANUAL SEARCH PAGE ---
elif page == "Manual Search":
    st.title("🔍 Manual Database Search")
    
    query = st.text_input("Enter drug name...", placeholder="e.g. panadol extra")
    
    # Columns Selector
    with st.expander("Select Info to Display"):
        all_cols = db_df.columns.tolist()
        defaults = ['name_en', 'price_retail', 'price_wholesale', 'barcode_primary', 'manufacturer']
        defaults = [c for c in defaults if c in all_cols]
        show_cols = st.multiselect("Columns", all_cols, default=defaults)
    
    if query:
        results = matcher_v2.search_live(query, limit=50)
        
        if results:
            res_df = pd.DataFrame(results)
            # Filter cols
            valid_cols = [c for c in show_cols if c in res_df.columns]
            st.dataframe(res_df[valid_cols], use_container_width=True)
            
            # Copy Helper (Streamlit dataframe has built-in copy in CSV usually, 
            # but we can provide a text area for copy-paste)
            
            st.subheader("Copy Data (Tab Separated)")
            st.caption("Click inside, Ctrl+A to select all, Ctrl+C to copy")
            tsv = res_df[valid_cols].to_csv(sep="\t", index=False)
            st.text_area("", value=tsv, height=150)
            
        else:
            st.warning("No matches found.")
