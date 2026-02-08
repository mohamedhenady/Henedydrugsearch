import customtkinter as ctk # type: ignore
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional
import json
import threading
import os
import matcher_v2 # type: ignore

# --- Theme Configuration ---
def load_initial_theme():
    # Placeholder for persistent settings - default to Dark for premium feel
    return "Dark"

ctk.set_appearance_mode(load_initial_theme())
ctk.set_default_color_theme("blue")

class DrugWizardApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window Setup
        self.title("Drug Matched Pro")
        self.geometry("900x700")
        
        # Grid Configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Config & State
        self.base_path = matcher_v2.get_base_path()
        self.config_path = os.path.join(self.base_path, 'config.json')
        self.db_fields = self.load_db_fields()
        
        # Wizard State
        self.input_file = ""
        self.headers = []
        self.selected_local_fields = []
        self.selected_db_fields = []
        self.search_column_var = ctk.StringVar()
        self.format_var = ctk.StringVar(value="xlsx")
        
        # Search State
        self.search_results = []
        self.selected_columns_vars = {}
        
        # Treeview holder
        self.tree: Optional[ttk.Treeview] = None
        self.context_menu: Optional[tk.Menu] = None
        
        # --- UI Layout ---
        self.create_sidebar()
        self.create_main_area()
        
        # Start at Wizard
        self.show_wizard()

    def load_db_fields(self):
        if not os.path.exists(self.config_path):
            return []
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('fields', [])
        except:
            return []

    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=160, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)
        
        logo_label = ctk.CTkLabel(self.sidebar, text="💊 DrugMatch", font=ctk.CTkFont(size=22, weight="bold"))
        logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        
        st_label = ctk.CTkLabel(self.sidebar, text="Pro Version", font=ctk.CTkFont(size=12, slant="italic"), text_color="gray")
        st_label.grid(row=1, column=0, padx=20, pady=(0, 20))
        
        self.btn_wizard = ctk.CTkButton(self.sidebar, text="File Wizard", command=self.show_wizard)
        self.btn_wizard.grid(row=2, column=0, padx=20, pady=10)
        
        self.btn_search = ctk.CTkButton(self.sidebar, text="Manual Search", command=self.show_search)
        self.btn_search.grid(row=3, column=0, padx=20, pady=10)
        
        # Theme Switcher
        lbl_theme = ctk.CTkLabel(self.sidebar, text="Appearance:", anchor="w")
        lbl_theme.grid(row=7, column=0, padx=20, pady=(10, 0))
        self.theme_menu = ctk.CTkOptionMenu(self.sidebar, values=["Light", "Dark", "System"], command=self.change_appearance_mode)
        self.theme_menu.grid(row=8, column=0, padx=20, pady=(0, 10))
        self.theme_menu.set("Dark")
        
        # Preload DB Button
        self.btn_load_db = ctk.CTkButton(self.sidebar, text="Reload JSON Data", command=self.reload_db, fg_color="#1f6aa5")
        self.btn_load_db.grid(row=9, column=0, padx=20, pady=20)

    def change_appearance_mode(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
    def clear_main(self):
        # Explicitly destroy tree widget if it exists to avoid lingering references
        tree = self.tree
        if tree is not None:
            try:
                tree.destroy()
            except:
                pass
            self.tree = None
            
        for widget in self.main_frame.winfo_children():
            widget.destroy()

    def reload_db(self):
        threading.Thread(target=self._reload_db_thread, daemon=True).start()
        
    def _reload_db_thread(self):
        try:
            matcher_v2.get_master_db(status_callback=lambda x: print(x))
            messagebox.showinfo("Success", "Database loaded/reloaded successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load DB: {e}")

    # ==========================
    # MODE 1: FILE WIZARD
    # ==========================
    def show_wizard(self):
        self.clear_main()
        self.btn_wizard.configure(fg_color=("gray75", "gray25")) # Active look
        self.btn_search.configure(fg_color="#3a7ebf") # Default ctk blue
        self.wizard_step_1()

    def wizard_step_1(self):
        self.clear_main()
        ctk.CTkLabel(self.main_frame, text="Step 1: Upload File", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(10, 5))
        
        self.file_card = ctk.CTkFrame(self.main_frame)
        self.file_card.pack(fill="x", pady=20)
        
        self.file_label = ctk.CTkLabel(self.file_card, text=self.input_file if self.input_file else "No file selected")
        self.file_label.pack(pady=10)
        
        ctk.CTkButton(self.file_card, text="Browse", command=self.browse_file).pack(pady=10)
        
        self.mapping_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.mapping_frame.pack(fill="x", pady=10)
        
        if self.headers:
            self.build_mapping_options()
            
        ctk.CTkButton(self.main_frame, text="Next ->", command=self.wizard_step_2).pack(side="bottom", anchor="e")

    def browse_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Data Files", "*.xlsx *.csv")])
        if filename:
            self.input_file = filename
            basename = os.path.basename(filename)
            self.file_label.configure(text=f"Selected: {basename}", text_color="green")
            try:
                self.headers = matcher_v2.get_file_headers(filename)
                self.build_mapping_options()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def build_mapping_options(self):
        for w in self.mapping_frame.winfo_children(): w.destroy()
        ctk.CTkLabel(self.mapping_frame, text="Search Column:").pack(anchor="w")
        self.search_column_var.set(self.headers[0] if self.headers else "")
        ctk.CTkOptionMenu(self.mapping_frame, variable=self.search_column_var, values=self.headers).pack(fill="x")

    def wizard_step_2(self):
        if not self.headers: return
        self.clear_main()
        ctk.CTkLabel(self.main_frame, text="Step 2: Select Columns", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)
        
        tab = ctk.CTkTabview(self.main_frame)
        tab.pack(fill="both", expand=True)
        tab.add("Your File")
        tab.add("Master DB")
        
        self.local_vars = self.create_checklist(tab.tab("Your File"), self.headers, preselect=True)
        db_keys = [f['key'] for f in self.db_fields]
        self.db_vars = self.create_checklist(tab.tab("Master DB"), db_keys, preselect_subset=['price_retail', 'barcode_primary', 'active_ingredients'])
        
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)
        ctk.CTkButton(btn_frame, text="Back", command=self.wizard_step_1, fg_color="gray").pack(side="left")
        ctk.CTkButton(btn_frame, text="Next", command=self.wizard_step_3).pack(side="right")

    def create_checklist(self, parent, items, preselect=False, preselect_subset=None):
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)
        vars_dict = {}
        for item in items:
            val = preselect
            if preselect_subset and item in preselect_subset: val = True
            v = ctk.BooleanVar(value=val)
            vars_dict[item] = v
            ctk.CTkCheckBox(scroll, text=item, variable=v).pack(anchor="w", pady=2)
        return vars_dict

    def wizard_step_3(self):
        self.selected_local_fields = [k for k,v in self.local_vars.items() if v.get()]
        self.selected_db_fields = [k for k,v in self.db_vars.items() if v.get()]
        
        self.clear_main()
        ctk.CTkLabel(self.main_frame, text="Step 3: Export", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=10)
        
        ctk.CTkRadioButton(self.main_frame, text="Excel", variable=self.format_var, value="xlsx").pack(pady=5)
        ctk.CTkRadioButton(self.main_frame, text="JSON", variable=self.format_var, value="json").pack(pady=5)
        
        self.prog = ctk.CTkProgressBar(self.main_frame)
        self.prog.pack(fill="x", pady=20)
        self.prog.set(0)
        
        self.status = ctk.CTkLabel(self.main_frame, text="Ready")
        self.status.pack()
        
        ctk.CTkButton(self.main_frame, text="Run", command=self.run_wizard).pack(pady=20)
        ctk.CTkButton(self.main_frame, text="Back", command=self.wizard_step_2, fg_color="gray").pack(side="bottom", anchor="w")

    def run_wizard(self):
        self.status.configure(text="Processing...")
        threading.Thread(target=self.worker_run, daemon=True).start()

    def worker_run(self):
        try:
            matcher_v2.run_matching_v2(
                self.input_file, self.search_column_var.get(),
                self.selected_local_fields, self.selected_db_fields,
                self.format_var.get(),
                progress_callback=lambda c,t: self.prog.set(c/t),
                status_callback=lambda m: self.status.configure(text=m)
            )
            self.status.configure(text="Done!", text_color="green")
            messagebox.showinfo("Success", "Finished!")
        except Exception as e:
            self.status.configure(text=f"Error: {e}", text_color="red")

    # ==========================
    # MODE 2: MANUAL SEARCH
    # ==========================
    def show_search(self):
        self.clear_main()
        self.btn_search.configure(fg_color=("gray75", "gray25"))
        self.btn_wizard.configure(fg_color="#3a7ebf")

        # Top Bar: Search Input & Run
        top_frame = ctk.CTkFrame(self.main_frame)
        top_frame.pack(fill="x", pady=(0, 10))
        
        self.entry_search = ctk.CTkEntry(top_frame, placeholder_text="Type drug name...")
        self.entry_search.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.entry_search.bind("<Return>", lambda e: self.do_search())
        
        ctk.CTkButton(top_frame, text="Search", width=100, command=self.do_search).pack(side="right", padx=10)

        # Columns Visibility Toggle
        self.col_frame = ctk.CTkFrame(self.main_frame, height=0) 
        
        self.cols_frame_container = ctk.CTkScrollableFrame(self.main_frame, height=100, label_text="Columns to Display & Copy")
        self.cols_frame_container.pack(fill="x", pady=5)
        
        # Populate columns
        default_cols = ['name_en', 'price_retail', 'price_wholesale', 'barcode_primary', 'manufacturer']
        all_keys = [f['key'] for f in self.db_fields]
        self.search_col_vars = {}
        
        # Grid layout for checkboxes
        for i, key in enumerate(all_keys):
            v = ctk.BooleanVar(value=key in default_cols)
            self.search_col_vars[key] = v
            cb = ctk.CTkCheckBox(self.cols_frame_container, text=key, variable=v, command=self.refresh_tree_columns)
            cb.grid(row=i//4, column=i%4, sticky="w", padx=5, pady=2)

        # Results Table (Treeview)
        tree_frame = ctk.CTkFrame(self.main_frame)
        tree_frame.pack(fill="both", expand=True, pady=5)
        
        # Style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b", foreground="white", rowheight=30)
        style.configure("Treeview.Heading", background="#1f1f1f", foreground="white", relief="flat")
        style.map("Treeview", background=[('selected', '#1f6aa5')])
        
        self.tree = ttk.Treeview(tree_frame, selectmode="extended", show="headings")
        
        _tree = self.tree
        if _tree is not None:
            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=_tree.yview)
            hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=_tree.xview)
            _tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            
            _tree.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            hsb.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Context Menu
        _tree = self.tree
        if _tree is not None:
            menu = tk.Menu(_tree, tearoff=0)
            menu.add_command(label="Copy Cell Value", command=self.copy_cell)
            menu.add_command(label="Copy Row (For Excel)", command=self.copy_row)
            _tree.bind("<Button-3>", self.show_context_menu)
            self.context_menu = menu

        # Init Cols
        self.refresh_tree_columns()

    def refresh_tree_columns(self):
        # Safety check if tree exists
        if not self.tree: return
        
        try:
            # Get selected columns
            active_cols = [k for k, v in self.search_col_vars.items() if v.get()]
            if not active_cols: active_cols = ['name_en'] # Fallback
            
            _tree = self.tree
            if _tree is not None:
                _tree["columns"] = active_cols
                for col in active_cols:
                    _tree.heading(col, **{"text": str(col)})
                    _tree.column(col, width=120, anchor="w")
                
            # If we have results, re-render them
            if self.search_results:
                self.populate_tree()
        except Exception as e:
            print(f"Error refreshing columns: {e}")

    def do_search(self):
        query = self.entry_search.get()
        if not query: return
        
        # Run in thread
        self.btn_search.configure(state="disabled")
        threading.Thread(target=self._search_thread, args=(query,), daemon=True).start()
        
    def _search_thread(self, query):
        try:
            # Need to ensure DB is loaded (get_master_db handles caching)
            results = matcher_v2.search_live(query, limit=100)
            self.search_results = results
            self.after(0, self.on_search_done)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error", str(e)))
            self.after(0, lambda: self.btn_search.configure(state="normal"))

    def on_search_done(self):
        self.populate_tree()
        self.btn_search.configure(state="normal")
        
    def populate_tree(self):
        _tree = self.tree
        if _tree is None: return
        
        _tree.delete(*_tree.get_children())
        active_cols = [k for k, v in self.search_col_vars.items() if v.get()]
        
        for row in self.search_results:
            values = [row.get(col, "") for col in active_cols]
            _tree.insert("", "end", values=values)

    def show_context_menu(self, event):
        _tree = self.tree
        menu = self.context_menu
        if _tree is None or menu is None: return 
        item = _tree.identify_row(event.y) # type: ignore
        if item:
            _tree.selection_set(item) # type: ignore
            menu.post(event.x_root, event.y_root) # type: ignore

    def copy_cell(self):
        _tree = self.tree
        if _tree is None: return
        sel = _tree.selection()
        if not sel: return
        vals = _tree.item(sel[0])['values']
        # Just copy the first visible value for now
        self.clipboard_clear()
        self.clipboard_append(str(vals[0])) 
        
    def copy_row(self):
        _tree = self.tree
        if _tree is None: return
        sel = _tree.selection()
        if not sel: return
        
        # Build TSV string for all selected rows
        rows_text = []
        for item in sel:
            vals = _tree.item(item)['values']
            # Convert None to empty, and join with tabs
            tsv = "\t".join([str(v) if v is not None else "" for v in vals])
            rows_text.append(tsv)
            
        full_text = "\n".join(rows_text)
        self.clipboard_clear()
        self.clipboard_append(full_text)
        messagebox.showinfo("Copied", "Row(s) copied to clipboard! You can paste directly into Excel.")

if __name__ == "__main__":
    app = DrugWizardApp()
    app.mainloop()
