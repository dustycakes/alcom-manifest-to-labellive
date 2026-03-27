# Dependencies: streamlit, pdfplumber, pandas, openpyxl, requests
# Install: pip install streamlit pdfplumber pandas openpyxl requests
# Run: streamlit run Alcom_Manifest_LabelLive.py

import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
from datetime import datetime
from custom_descriptions import CustomDescriptionLookup

# ============================================================================
# CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="Alcom Bonner MT – Manifest → Label LIVE",
    page_icon="📦",
    layout="wide"
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_manifest_number(text: str) -> str:
    """Extract manifest number from PDF text content."""
    patterns = [
        r'MANIFEST\s*NUMBER\s*\n?\s*([A-Z0-9\-]+)',
        r'Manifest\s*#?\s*[:\-]?\s*([A-Z0-9\-]+)',
        r'MANIFEST\s*NO\.?\s*[:\-]?\s*([A-Z0-9\-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def split_cell_by_newlines(cell: str) -> list[str]:
    """Split a cell content by newlines, clean up each part."""
    if not cell:
        return []
    return [part.strip() for part in cell.split('\n') if part.strip()]


def extract_bunks_from_row(sku_cell: str, ticket_cell: str, shipment_cell: str) -> list[dict]:
    """
    Extract bunks from a table row - SKU and QTY only.
    
    Returns list of {"sku": str, "qty": int, "ticket": str}
    """
    bunks = []
    
    skus = split_cell_by_newlines(sku_cell)
    tickets_raw = split_cell_by_newlines(ticket_cell) if ticket_cell else []
    shipments_raw = split_cell_by_newlines(shipment_cell) if shipment_cell else []
    
    # Filter to valid SKUs
    valid_skus = [s for s in skus if re.match(r'^\d{2}-\d{5}-\d{4}$', s)]
    
    # Extract tickets (5-6 digits, not starting with 23)
    valid_tickets = []
    for t in tickets_raw:
        if re.match(r'^\d{5,6}$', t) and not t.startswith('23'):
            valid_tickets.append(t)
    
    # Extract shipments (quantities)
    valid_shipments = []
    for s in shipments_raw:
        s_clean = s.replace(',', '')
        if re.match(r'^\d+$', s_clean):
            qty = int(s_clean)
            if 0 < qty < 500:  # Filter out totals
                valid_shipments.append(qty)
    
    # Group tickets and shipments by item (using totals as delimiters)
    def extract_groups(values, is_numeric=False):
        groups = []
        current = []
        for val in values:
            if is_numeric:
                val_clean = str(val).replace(',', '')
                if re.match(r'^\d+$', val_clean):
                    num = int(val_clean)
                    if num > 500:
                        if current:
                            groups.append(current)
                            current = []
                    else:
                        current.append(num)
            else:
                if re.match(r'^\d{5,6}$', val) and not val.startswith('23'):
                    current.append(val)
                elif re.match(r'^\d+$', val):
                    if current:
                        groups.append(current)
                        current = []
        if current:
            groups.append(current)
        return groups
    
    ticket_groups = extract_groups(valid_tickets, is_numeric=False)
    shipment_groups = extract_groups(valid_shipments, is_numeric=True)
    
    # Create bunks
    for i, sku in enumerate(valid_skus):
        item_tickets = ticket_groups[i] if i < len(ticket_groups) else []
        item_shipments = shipment_groups[i] if i < len(shipment_groups) else []
        
        for j in range(min(len(item_tickets), len(item_shipments))):
            bunks.append({
                "SKU": sku,
                "QTY_pieces": item_shipments[j],
                "TICKET": item_tickets[j]
            })
    
    return bunks


def extract_tickets_from_text(text: str) -> list[tuple[str, int, str]]:
    """
    Extract ticket/qty pairs from text (fallback for Apel 2 format).
    Pattern: 647265 18 428  <- ticket, qty, weight
    """
    tickets = []
    lines = text.split('\n')
    current_sku = None

    for line in lines:
        sku_match = re.search(r'(\d{2}-\d{5}-\d{4})', line)
        if sku_match:
            current_sku = sku_match.group(1)

        words = line.split()
        for i, word in enumerate(words):
            ticket_match = re.match(r'^(64|65)\d{4}$', word)
            if ticket_match:
                ticket_num = word
                if ticket_num.startswith('23'):
                    continue

                for j in range(i + 1, min(i + 3, len(words))):
                    qty_word = words[j].replace(',', '')
                    qty_match = re.match(r'^(\d+)$', qty_word)
                    if qty_match:
                        qty_num = int(qty_match.group(1))
                        if 0 < qty_num < 1000:
                            tickets.append((ticket_num, qty_num, current_sku))
                            break

    return tickets


def parse_manifest_pdf(pdf_file) -> tuple[pd.DataFrame, list]:
    """
    Parse manifest PDF - extract SKU, QTY, and TICKET only.
    Uses text-based extraction which correctly associates SKUs with tickets.
    """
    all_text = ""
    debug_info = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"

    # Use text-based extraction as primary method
    tickets_from_text = extract_tickets_from_text(all_text)
    debug_info.append(f"Extracted {len(tickets_from_text)} tickets from text")

    # Group by SKU
    tickets_by_sku = {}
    for ticket, qty, sku_context in tickets_from_text:
        if sku_context:
            if sku_context not in tickets_by_sku:
                tickets_by_sku[sku_context] = []
            tickets_by_sku[sku_context].append((ticket, qty))

    # Create bunks
    bunks = []
    for sku, ticket_qtys in tickets_by_sku.items():
        for ticket, qty in ticket_qtys:
            bunks.append({
                "SKU": sku,
                "QTY_pieces": qty,
                "TICKET": ticket
            })

    debug_info.append(f"Total bunks: {len(bunks)}")
    debug_info.append(f"Unique SKUs: {len(tickets_by_sku)}")

    df = pd.DataFrame(bunks)
    return df, debug_info


def create_excel_output(df: pd.DataFrame, manifest_number: str, lookup: CustomDescriptionLookup) -> BytesIO:
    """Create Excel file with custom descriptions from lookup table."""
    output = BytesIO()
    
    # Add custom descriptions from lookup table
    export_df = df[["SKU", "QTY_pieces"]].copy()
    export_df.insert(1, "DESCRIPTION", "")
    
    for idx, row in export_df.iterrows():
        custom_desc = lookup.get_custom_description(row["SKU"])
        if custom_desc:
            export_df.at[idx, "DESCRIPTION"] = custom_desc
        else:
            # Fallback: use SKU as description if not in lookup
            export_df.at[idx, "DESCRIPTION"] = f"SKU: {row['SKU']}"
    
    export_df.columns = ["SKU", "DESCRIPTION", "QTY"]
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        export_df.to_excel(writer, index=False, sheet_name='Labels')
    
    output.seek(0)
    return output


# ============================================================================
# SESSION STATE
# ============================================================================

if 'manifest_df' not in st.session_state:
    st.session_state.manifest_df = pd.DataFrame()
if 'manifest_number' not in st.session_state:
    st.session_state.manifest_number = ""
if 'processed' not in st.session_state:
    st.session_state.processed = False
if 'debug_info' not in st.session_state:
    st.session_state.debug_info = []

# Initialize custom description lookup
if 'description_lookup' not in st.session_state:
    st.session_state.description_lookup = CustomDescriptionLookup()

# ============================================================================
# MAIN UI
# ============================================================================

st.title("Alcom Bonner MT – Manifest → Label LIVE")
st.markdown("---")

# Create tabs
tab1, tab2 = st.tabs(["📦 Manifest Processing", "📝 Custom Descriptions"])

with tab1:
    st.header("Process Manifest PDF")
    
    # Sidebar controls
    with st.sidebar:
        st.header("Settings")
        
        default_labels = st.number_input(
            "Default Labels per Bunk",
            min_value=1,
            value=2,
            step=1
        )
        
        if st.button("Apply to All", use_container_width=True):
            if not st.session_state.manifest_df.empty:
                st.session_state.manifest_df["Labels_to_Print"] = default_labels
                st.rerun()
        
        st.divider()
        st.markdown("### Instructions")
        st.markdown("""
        1. Upload APEL Extrusions manifest PDF
        2. Review extracted SKUs and quantities
        3. Edit descriptions if needed
        4. Download Excel for Label LIVE
        """)
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Upload APEL Extrusions Manifest PDF",
        type=['pdf'],
        help="Upload the manifest PDF from APEL Extrusions"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        process_btn = st.button("Process Manifest", type="primary", use_container_width=True)
    with col2:
        if st.session_state.processed:
            if st.button("Clear & Start New", use_container_width=True):
                st.session_state.manifest_df = pd.DataFrame()
                st.session_state.manifest_number = ""
                st.session_state.processed = False
                st.rerun()
    
    # Process manifest
    if process_btn and uploaded_file:
        try:
            df, debug_info = parse_manifest_pdf(uploaded_file)
            
            if not df.empty:
                df["Labels_to_Print"] = default_labels
                st.session_state.manifest_df = df
                st.session_state.manifest_number = extract_manifest_number(uploaded_file.read().decode('latin-1', errors='ignore'))
                st.session_state.processed = True
                st.session_state.debug_info = debug_info
                st.rerun()
            else:
                st.warning("No data extracted from PDF. Please check the file format.")
        except Exception as e:
            st.error(f"Error processing PDF: {str(e)}")
    
    # Display results
    if st.session_state.processed and not st.session_state.manifest_df.empty:
        lookup = st.session_state.description_lookup
        
        # Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            total_labels = int(st.session_state.manifest_df["Labels_to_Print"].sum())
            st.metric("🏷️ Total Labels", total_labels)
        with col2:
            total_bunks = len(st.session_state.manifest_df)
            st.metric("📦 Total Bunks", total_bunks)
        with col3:
            total_pieces = int(st.session_state.manifest_df["QTY_pieces"].sum())
            st.metric("🔧 Total Pieces", total_pieces)
        
        st.markdown("---")
        
        # Show data with custom descriptions
        st.subheader("Manifest Data")
        
        display_df = st.session_state.manifest_df.copy()
        
        # Add custom descriptions
        display_df["CUSTOM_DESC"] = display_df["SKU"].apply(
            lambda sku: lookup.get_custom_description(sku) or f"SKU: {sku}"
        )
        
        # Show editable table
        edit_df = st.data_editor(
            display_df[["SKU", "CUSTOM_DESC", "QTY_pieces", "Labels_to_Print"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "SKU": st.column_config.TextColumn("SKU", width="medium"),
                "CUSTOM_DESC": st.column_config.TextColumn("Description", width="large",
                    help="From lookup table - edit directly or update in Custom Descriptions tab"),
                "QTY_pieces": st.column_config.NumberColumn("QTY", min_value=0, width="small"),
                "Labels_to_Print": st.column_config.NumberColumn("Labels", min_value=1, width="small"),
            }
        )
        
        # Update session state
        st.session_state.manifest_df["Labels_to_Print"] = edit_df["Labels_to_Print"]
        st.session_state.manifest_df["QTY_pieces"] = edit_df["QTY_pieces"]
        for idx, row in edit_df.iterrows():
            if idx < len(st.session_state.manifest_df):
                # Store custom description override
                pass
        
        st.divider()
        
        # Export
        st.subheader("📥 Export")
        
        # Use edited data for export
        export_df = st.session_state.manifest_df.copy()
        export_df["DESCRIPTION"] = edit_df["CUSTOM_DESC"]
        
        excel_data = create_excel_output(export_df, st.session_state.manifest_number, lookup)
        filename = f"LabelLIVE_{st.session_state.manifest_number}.xlsx"
        
        st.download_button(
            label="Download Excel for Label LIVE",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            type="primary"
        )
        
        # Debug info
        if st.session_state.debug_info:
            with st.expander("🔍 Debug Info"):
                for line in st.session_state.debug_info:
                    st.text(line)
    
    elif uploaded_file and not st.session_state.processed:
        st.info("Click 'Process Manifest' to extract data.")

with tab2:
    st.header("Custom Description Lookup Table")
    st.markdown("""
    Manage SKU to custom description mappings. These descriptions will be used 
    when generating Label LIVE Excel files.
    """)
    
    lookup = st.session_state.description_lookup
    
    # Upload/refresh lookup table
    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded_lookup = st.file_uploader(
            "Upload updated lookup table (optional)",
            type=['xlsx', 'xls'],
            key="lookup_uploader"
        )
    with col2:
        if uploaded_lookup:
            try:
                new_df = pd.read_excel(uploaded_lookup)
                new_df.columns = [col.strip().upper() for col in new_df.columns]
                lookup.df = new_df
                st.success("Lookup table updated!")
            except Exception as e:
                st.error(f"Error loading file: {e}")
    
    st.divider()
    
    # Search/filter
    search_query = st.text_input("🔍 Search SKUs or descriptions", placeholder="Enter SKU or description...")
    
    if search_query:
        filtered_df = lookup.search(search_query)
    else:
        filtered_df = lookup.get_all_descriptions()
    
    # Show missing descriptions
    missing_count = len(lookup.get_missing_custom_descriptions())
    if missing_count > 0:
        st.warning(f"⚠️ {missing_count} SKUs missing custom descriptions")
    
    # Display editable table
    st.subheader(f"Descriptions ({len(filtered_df)} shown)")
    
    edited_lookup = st.data_editor(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "GENIUS #": st.column_config.TextColumn("SKU (GENIUS #)", width="medium"),
            "CUSTOM DESCRIPTION": st.column_config.TextColumn("Custom Description", width="large"),
            "DESCRIPTION": st.column_config.TextColumn("Original Description", width="large"),
        }
    )
    
    # Save changes
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("💾 Save Changes", type="primary", use_container_width=True):
            lookup.df = edited_lookup
            lookup.save()
            st.success("Saved!")
            st.rerun()
    
    with col2:
        if st.button("🔄 Reload from File", use_container_width=True):
            lookup._load()
            st.session_state.description_lookup = lookup
            st.rerun()
    
    # Add new entry
    st.divider()
    st.subheader("Add New Entry")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        new_sku = st.text_input("SKU (GENIUS #)", key="new_sku")
    with col2:
        new_custom_desc = st.text_input("Custom Description", key="new_custom_desc")
    with col3:
        new_orig_desc = st.text_input("Original Description", key="new_orig_desc")
    
    if st.button("Add Entry"):
        if new_sku and new_custom_desc:
            lookup.add_or_update(new_sku, new_custom_desc, new_orig_desc)
            lookup.save()
            st.success(f"Added/updated {new_sku}")
            st.rerun()
        else:
            st.error("SKU and Custom Description are required")
