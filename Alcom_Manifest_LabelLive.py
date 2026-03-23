# Dependencies: streamlit, pdfplumber, pandas, openpyxl, requests
# Install: pip install streamlit pdfplumber pandas openpyxl requests
# Run: streamlit run Alcom_Manifest_LabelLive.py

import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO
from datetime import datetime

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
    # Look for MANIFEST NUMBER header followed by value
    patterns = [
        r'MANIFEST\s*NUMBER\s*\n?\s*([A-Z0-9\-]+)',
        r'Manifest\s*#?\s*[:\-]?\s*([A-Z0-9\-]+)',
        r'MANIFEST\s*NO\.?\s*[:\-]?\s*([A-Z0-9\-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    # Fallback: use timestamp
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def smart_shorten_description(desc: str, max_len: int = 40) -> str:
    """
    Smart DESCRIPTION shortening for label printing.
    
    APEL Extrusions format: "TUBE, 01.000x01.500x.080x99.00 6005A/T5"
    
    Strategy:
    - Keep "TUBE" prefix
    - Extract key dimensions (outer dimensions and length)
    - Format like: "TUBE 1.0x1.5x99" or "2X7 @312" style
    - Remove alloy/temper unless critical
    
    TUNE THIS: Adjust max_len and formatting based on label printer constraints
    """
    if not desc:
        return ""
    
    # Normalize whitespace
    desc = ' '.join(desc.split())
    
    # Check if it starts with TUBE
    is_tube = desc.upper().startswith('TUBE')
    
    # Extract dimensions pattern: numbers with x between them
    # Pattern: 01.000x01.500x.080x99.00 or similar
    dim_match = re.search(r'([\d.]+)x([\d.]+)x([\d.]+)x([\d.]+)', desc)
    if dim_match:
        d1, d2, d3, length = dim_match.groups()
        # Clean up leading zeros: 01.000 -> 1.0
        d1 = str(float(d1))
        d2 = str(float(d2))
        d3 = str(float(d3))
        length = str(float(length))
        
        # Format: TUBE 1.0x1.5x0.08x99 or shortened
        if is_tube:
            result = f"TUBE {d1}x{d2}x{d3}x{length}"
        else:
            result = f"{d1}x{d2}x{d3}x{length}"
        
        if len(result) > max_len:
            # Ultra-short: just outer dims and length
            result = f"TUBE {d1}x{d2}@{length}"
        
        return result
    
    # Fallback: generic shortening
    # Remove alloy/temper suffix (e.g., "6005A/T5")
    desc = re.sub(r'\s*6005A/T5\s*', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r'\s*6063-T5\s*', '', desc, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    desc = ' '.join(desc.split())
    
    # Trim to max length
    if len(desc) > max_len:
        desc = desc[:max_len-3] + "..."
    
    return desc.strip()


def parse_manifest_pdf(pdf_file) -> tuple[pd.DataFrame, str]:
    """
    Parse APEL Extrusions manifest PDF using pdfplumber.

    APEL Manifest table structure:
    | ITEM NO. | DIE NUMBER | CUSTOMER PART NO. | DESCRIPTION ALLOY/TEMPER | LENGTH | FINISH |
      ORDERED PIECES | ORDERED POUNDS | BACKORDERED PIECES | BACKORDERED POUNDS |
      TICKET | THIS SHIPMENT PIECES | THIS SHIPMENT POUNDS |

    Each ITEM can have multiple TICKET rows (bunks) listed vertically.
    We use text extraction with coordinates to find ticket/qty pairs,
    and match them to items by vertical position.

    Returns:
        tuple: (DataFrame with bunks, manifest_number string)
    """
    all_text = ""
    bunks = []
    items = []  # Store item data with y-position for matching

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # Extract text for manifest number
            text = page.extract_text()
            if text:
                all_text += text + "\n"

            page_height = page.height

            # Extract tables to get ITEM rows with SKU and DESCRIPTION
            tables = page.extract_tables()

            for table in tables:
                # Find header row
                header_row = None
                header_indices = {}

                for row_idx, row in enumerate(table):
                    if row and any(cell and 'CUSTOMER PART' in str(cell).upper() for cell in row):
                        header_row = row_idx
                        for col_idx, cell in enumerate(row):
                            if cell:
                                cell_str = str(cell).strip().upper()
                                if 'CUSTOMER PART' in cell_str:
                                    header_indices['sku'] = col_idx
                                elif 'DESCRIPTION' in cell_str or 'ALLOY' in cell_str:
                                    header_indices['description'] = col_idx
                                elif 'ITEM' in cell_str and 'NO' in cell_str:
                                    header_indices['item'] = col_idx
                        break

                if header_row is None:
                    continue

                # Get table bbox for text extraction
                table_bbox = None

                # Parse item rows - collect SKU, DESC, and y-position range
                current_sku = None
                current_desc = None
                current_item = None
                item_y_top = None
                item_y_bottom = None

                for row_idx in range(header_row + 1, len(table)):
                    row = table[row_idx]
                    if not row:
                        continue

                    row_clean = [str(cell).strip() if cell else "" for cell in row]

                    # Check for new ITEM NO.
                    item_val = ""
                    if 'item' in header_indices and header_indices['item'] < len(row_clean):
                        item_val = row_clean[header_indices['item']]
                        if item_val and item_val.isdigit():
                            # Save previous item if exists
                            if current_sku and item_y_top is not None:
                                items.append({
                                    "sku": current_sku,
                                    "desc": current_desc,
                                    "y_top": item_y_top,
                                    "y_bottom": item_y_bottom
                                })
                            current_item = item_val
                            item_y_top = None
                            item_y_bottom = None

                    # Get SKU - extract first valid pattern
                    if 'sku' in header_indices and header_indices['sku'] < len(row_clean):
                        sku_candidate = row_clean[header_indices['sku']]
                        sku_match = re.search(r'(\d{2}-\d{5}-\d{4})', str(sku_candidate))
                        if sku_match:
                            current_sku = sku_match.group(1)

                    # Get Description - look for TUBE
                    if 'description' in header_indices and header_indices['description'] < len(row_clean):
                        desc_candidate = row_clean[header_indices['description']]
                        if desc_candidate and 'TUBE' in str(desc_candidate).upper():
                            current_desc = str(desc_candidate).strip()

                # Save last item
                if current_sku:
                    items.append({
                        "sku": current_sku,
                        "desc": current_desc,
                        "y_top": item_y_top,
                        "y_bottom": item_y_bottom
                    })

            # Now extract text with positions to find ticket/qty pairs
            # and match them to items
            if items:
                # Extract words with positions
                words = page.extract_words()

                # Find ticket numbers and quantities by position
                # Ticket column is typically to the right, quantity is rightmost
                page_width = page.width

                # Group words by line (similar y-coordinate)
                lines = {}
                for word in words:
                    y_key = round(word['top'] / 5) * 5  # Group by 5-pixel bands
                    if y_key not in lines:
                        lines[y_key] = []
                    lines[y_key].append(word)

                # For each line, look for ticket + quantity pattern
                ticket_data = []  # (y_position, ticket, qty)
                for y_pos, line_words in sorted(lines.items()):
                    # Sort words by x position (left to right)
                    line_words.sort(key=lambda w: w['x0'])

                    # Look for ticket (5-6 digits) followed by quantity
                    for i, word in enumerate(line_words):
                        text = word['text'].strip()
                        # Check for ticket number
                        ticket_match = re.match(r'^(\d{5,6})$', text)
                        if ticket_match:
                            ticket_num = ticket_match.group(1)
                            # Look for quantity in next few words (to the right)
                            for j in range(i + 1, min(i + 4, len(line_words))):
                                qty_word = lines[y_pos][j]['text'].strip()
                                qty_match = re.match(r'^(\d+)$', qty_word)
                                if qty_match:
                                    qty_num = int(qty_match.group(1))
                                    if qty_num > 0 and qty_num < 10000:  # Reasonable quantity
                                        ticket_data.append((y_pos, ticket_num, qty_num))
                                        break

                # Match tickets to items by y-position
                # Simple approach: assign tickets to items in order
                if ticket_data and items:
                    tickets_per_item = len(ticket_data) // len(items) if items else 0

                    for i, (y_pos, ticket_num, qty_num) in enumerate(ticket_data):
                        # Find which item this ticket belongs to
                        item_idx = min(i // max(tickets_per_item, 1), len(items) - 1) if tickets_per_item > 0 else 0
                        item = items[item_idx]

                        bunk = {
                            "SKU": item["sku"],
                            "DESCRIPTION": smart_shorten_description(item["desc"] or ""),
                            "QTY_pieces": qty_num,
                            "TICKET": ticket_num,
                            "Labels_to_Print": 2
                        }
                        bunks.append(bunk)

    manifest_number = extract_manifest_number(all_text)

    # Show debug info if no bunks found
    if not bunks:
        st.warning("No bunk data found in PDF. Check PDF format or try manual entry.")
        with st.expander("Debug Info"):
            st.text(f"Total items found: {len(items)}")
            st.text(f"Items: {items[:5]}")

    df = pd.DataFrame(bunks)
    return df, manifest_number


def create_excel_output(df: pd.DataFrame, manifest_number: str) -> BytesIO:
    """
    Create Excel file for Label LIVE with exact headers.
    Output: 1 row per bunk, columns: SKU, DESCRIPTION, QTY
    """
    output = BytesIO()
    
    # Select and rename columns for output
    export_df = df[["SKU", "DESCRIPTION", "QTY_pieces"]].copy()
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


# ============================================================================
# MAIN UI
# ============================================================================

st.title("Alcom Bonner MT – Manifest → Label LIVE")
st.markdown("---")

# Sidebar controls
with st.sidebar:
    st.header("Settings")
    
    default_labels = st.number_input(
        "Default Labels per Bunk",
        min_value=1,
        value=2,
        step=1,
        help="Default number of labels to print per bunk"
    )
    
    if st.button("Apply to All", use_container_width=True):
        if not st.session_state.manifest_df.empty:
            st.session_state.manifest_df["Labels_to_Print"] = default_labels
            st.rerun()
    
    st.info("📝 **Note:** Labels_to_Print is for planning only. Final Excel = 1 row per bunk.")
    
    st.divider()
    st.markdown("### Instructions")
    st.markdown("""
    1. Upload APEL Extrusions manifest PDF
    2. Review and edit parsed data
    3. Adjust Labels_to_Print as needed
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

# Progress bar placeholder
progress_bar = st.progress(0)

# Process manifest
if process_btn and uploaded_file:
    progress_bar.progress(25, text="Reading PDF...")
    
    try:
        df, manifest_num = parse_manifest_pdf(uploaded_file)
        progress_bar.progress(75, text="Creating data table...")
        
        if not df.empty:
            # Apply default labels
            df["Labels_to_Print"] = default_labels
            st.session_state.manifest_df = df
            st.session_state.manifest_number = manifest_num
            st.session_state.processed = True
            progress_bar.progress(100, text="Complete!")
            st.rerun()
        else:
            st.warning("No data extracted from PDF. Please check the file format.")
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
    finally:
        progress_bar.empty()

# Display data editor and export
if st.session_state.processed and not st.session_state.manifest_df.empty:
    st.markdown("---")
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        total_labels = int(st.session_state.manifest_df["Labels_to_Print"].sum())
        st.metric("🏷️ Total Labels to Print", total_labels)
    with col2:
        total_bunks = len(st.session_state.manifest_df)
        st.metric("📦 Total Bunks", total_bunks)
    with col3:
        total_pieces = int(st.session_state.manifest_df["QTY_pieces"].sum())
        st.metric("🔧 Total Pieces", total_pieces)
    
    st.markdown("---")
    
    # Data editor
    st.subheader("Edit Manifest Data")

    # Define column order - exclude TICKET from display (internal tracking only)
    display_cols = ["SKU", "DESCRIPTION", "QTY_pieces", "Labels_to_Print"]
    available_cols = [c for c in display_cols if c in st.session_state.manifest_df.columns]

    edited_df = st.data_editor(
        st.session_state.manifest_df,
        use_container_width=True,
        hide_index=True,
        column_order=available_cols,
        column_config={
            "SKU": st.column_config.TextColumn("SKU", help="Customer Part Number", width="medium"),
            "DESCRIPTION": st.column_config.TextColumn("DESCRIPTION", help="Product description (editable)", width="large"),
            "QTY_pieces": st.column_config.NumberColumn("QTY_pieces", help="Quantity in pieces", min_value=0, width="small"),
            "Labels_to_Print": st.column_config.NumberColumn("Labels_to_Print", help="Number of labels to print", min_value=1, width="small"),
        },
        num_rows="dynamic"
    )
    
    # Update session state with edits
    st.session_state.manifest_df = edited_df
    
    # Recalculate total
    total_labels = int(edited_df["Labels_to_Print"].sum())
    
    st.divider()
    
    # Export section
    st.subheader("📥 Export")
    
    excel_data = create_excel_output(edited_df, st.session_state.manifest_number)
    filename = f"LabelLIVE_manifest_{st.session_state.manifest_number}.xlsx"
    
    st.download_button(
        label="Download Excel for Label LIVE",
        data=excel_data,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary"
    )
    
    st.caption(f"Filename: `{filename}`")
    st.caption("✅ Excel contains exactly 3 columns: SKU, DESCRIPTION, QTY (1 row per bunk)")

elif uploaded_file and not st.session_state.processed:
    st.info("Click 'Process Manifest' to extract bunk data from the PDF.")

# ============================================================================
# PHASE 2 – Direct Label LIVE API
# ============================================================================
# TODO: Implement direct API integration with Label LIVE system
# 
# Future enhancements:
# - POST directly to Label LIVE API endpoint
# - Receive print job confirmation
# - Track print history
# - Webhook for print completion status
#
# Example API call structure:
# ```python
# import requests
# 
# def send_to_label_live(df: pd.DataFrame):
#     payload = {
#         "labels": df[["SKU", "DESCRIPTION", "QTY"]].to_dict(orient="records"),
#         "copies_per_label": df["Labels_to_Print"].iloc[0] if len(df) > 0 else 1
#     }
#     response = requests.post(
#         "https://label-live.alcom.com/api/v1/print",
#         json=payload,
#         headers={"Authorization": f"Bearer {API_KEY}"}
#     )
#     return response.json()
# ```
# ============================================================================
