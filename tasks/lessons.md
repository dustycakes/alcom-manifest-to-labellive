# Lessons Learned - Alcom Manifest to Label LIVE

## Date: 2026-03-27

### Bug #4: Save Changes Overwrites Dataset with Filtered Results

**Problem:** "Save Changes" button assigned the filtered `edited_lookup` DataFrame directly to `lookup.df`, then saved. If user searched for one SKU and clicked Save, it overwrote the entire 334-row dataset with just the filtered results.

**Symptoms:**
- User adds new SKU via "Add Entry" → appears in table
- User searches to isolate the new SKU
- User clicks "Save Changes" (unsure if needed)
- Entire lookup table reduced to only the filtered/searched rows

**Root Cause:**
```python
# BUGGY CODE
if st.button("Save Changes"):
    lookup.df = edited_lookup  # Assigned filtered view to master
    lookup.save()              # Saved only filtered rows
```

**Solution:** Remove "Save Changes" button entirely. Implement auto-save that:
1. Compares edited rows against master `lookup.df` by SKU
2. Updates only changed rows in master dataframe
3. Saves full dataset (never the filtered view)
4. Shows toast notification on each save

**New UX:**
- Inline edits → auto-save immediately with ✓ toast
- Add Entry → auto-saves immediately (unchanged)
- Export button → download full lookup table for mass edits in Excel
- Upload → re-import edited Excel file

**Files:**
- `Alcom_Manifest_LabelLive.py` - Removed Save Changes + Reload buttons, added auto-save logic + Export

---

## Date: 2026-03-26

### Architecture Change: Custom Description Lookup Table

**Key Decision:** Separate SKU/QTY extraction from description management.

**Before:** Parsed descriptions from PDF, tried to shorten/normalize them.
**After:** Extract only SKU + QTY from PDF, look up custom descriptions from Excel file.

**Benefits:**
- Simpler PDF parsing (only need SKU and ticket/qty)
- Human-readable descriptions managed in Excel (`Manifest Description Conversion.xlsx`)
- Easy to update descriptions without code changes
- Fallback for unknown SKUs: `"SKU: {sku}"`

**Files:**
- `custom_descriptions.py` - Lookup module with `CustomDescriptionLookup` class
- `Manifest Description Conversion.xlsx` - 334 SKU mappings (GENIUS # → CUSTOM DESCRIPTION)

### Bug #3: Table Cell Extraction Fails for Apel 3 Format

**Problem:** Apel 3 PDF has merged cells with multiple SKUs/tickets per row. Cell-based extraction was incorrectly matching tickets to SKUs.

**Symptoms:**
- Apel 3 extracted only 3 unique SKUs instead of 14
- All tickets assigned to first SKU (70-11160-0990)
- Missing Page 1 item (SKU 70-11243-2640, Ticket 647532, QTY 116)

**Root Cause:**
- Table structure varies between manifests (Apel 1/2 vs Apel 3)
- Apel 3 has 4 SKUs in one cell, with tickets/shipments grouped by item with totals as delimiters
- Grouping logic couldn't handle all edge cases (e.g., shipment total `465` < 500 threshold)

**Solution:** Use **text-based extraction** as primary method instead of table cell extraction.

```python
# Text extraction pattern - tickets appear near their SKU in text flow
# Format: "70-11243-2640 ... 647532 116 646"
def extract_tickets_from_text(text: str):
    for line in lines:
        # Track current SKU context
        sku_match = re.search(r'(\d{2}-\d{5}-\d{4})', line)
        if sku_match:
            current_sku = sku_match.group(1)

        # Find tickets (64xxxx or 65xxxx) with qty next to them
        for word in words:
            if re.match(r'^(64|65)\d{4}$', word):
                # Next number is quantity
                ...
```

**Results:**
| Metric | Before | After |
|--------|--------|-------|
| Apel 3 bunks | 41 | 42 |
| Apel 3 unique SKUs | 3 | 14 |
| Page 1 item | Missing | ✓ Found |

### PDF Format Variations

**Apel 1/2 Format:**
- One item per table row
- Tickets in text below table
- Text extraction works well

**Apel 3 Format:**
- Multiple items per table row (merged cells)
- Tickets in table cells with totals as delimiters
- Text extraction MORE reliable than cell extraction

**Lesson:** Text-based extraction is more robust across format variations because the PDF text flow preserves SKU→ticket proximity regardless of table structure.

### Output Order Matches Manifest

**Issue:** Initial output grouped tickets by SKU, which made verification against the PDF difficult when the same SKU appeared on multiple pages.

**Solution:** Preserve the order from text extraction - tickets appear in output in the same order they appear in the manifest.

**Benefit:** Side-by-side verification with PDF is now straightforward - row N in output corresponds to the Nth ticket in the manifest.

### Key Patterns

```python
# SKU pattern
r'\d{2}-\d{5}-\d{4}'  # e.g., 70-11160-0990

# Ticket pattern (6 digits starting with 64 or 65)
r'^(64|65)\d{4}$'  # e.g., 647532

# Filter die numbers (start with 23)
if ticket.startswith('23'): continue

# Quantity pattern (small number after ticket)
r'^\d+$'  # 1-3 digits typically
```

### Debug Files

Saved to `debug ref/` folder:
- `Apel3_Output.xlsx` - Full extracted data with custom descriptions
- `Apel3_Summary.txt` - Text summary by SKU with ticket/qty pairs
- `Apel1_Analysis.md` - Analysis of multi-page manifest structure

### Commands

```bash
# Run locally
streamlit run Alcom_Manifest_LabelLive.py

# Test parsing
python3 -c "from Alcom_Manifest_LabelLive import parse_manifest_pdf; df, _ = parse_manifest_pdf(open('Manifests/Apel 3.PDF', 'rb')); print(len(df), 'bunks')"
```

---

## Date: 2026-03-23
                # Next number is quantity
                ...
```

**Results:**
| Metric | Before | After |
|--------|--------|-------|
| Apel 3 bunks | 41 | 42 |
| Apel 3 unique SKUs | 3 | 14 |
| Page 1 item | Missing | ✓ Found |

### PDF Format Variations

**Apel 1/2 Format:**
- One item per table row
- Tickets in text below table
- Text extraction works well

**Apel 3 Format:**
- Multiple items per table row (merged cells)
- Tickets in table cells with totals as delimiters
- Text extraction MORE reliable than cell extraction

**Lesson:** Text-based extraction is more robust across format variations because the PDF text flow preserves SKU→ticket proximity regardless of table structure.

### Key Patterns

```python
# SKU pattern
r'\d{2}-\d{5}-\d{4}'  # e.g., 70-11160-0990

# Ticket pattern (6 digits starting with 64 or 65)
r'^(64|65)\d{4}$'  # e.g., 647532

# Filter die numbers (start with 23)
if ticket.startswith('23'): continue

# Quantity pattern (small number after ticket)
r'^\d+$'  # 1-3 digits typically
```

### Debug Files

Saved to `debug ref/` folder:
- `Apel3_Output.xlsx` - Full extracted data with custom descriptions
- `Apel3_Summary.txt` - Text summary by SKU with ticket/qty pairs

### Commands

```bash
# Run locally
streamlit run Alcom_Manifest_LabelLive.py

# Test parsing
python3 -c "from Alcom_Manifest_LabelLive import parse_manifest_pdf; df, _ = parse_manifest_pdf(open('Manifests/Apel 3.PDF', 'rb')); print(len(df), 'bunks')"
```

---

## Date: 2026-03-23

### Bug #1: Data Lost Across Page Iterations

**CRITICAL: Accumulate data across ALL pages before processing**

The manifest PDF has multiple pages, and pdfplumber processes them in a loop. The bug that took the longest to fix was:

```python
# WRONG - ticket_data reset each page iteration
for page in pdf.pages:
    ticket_data = []  # BUG: Reset every page!
    # ... extract tickets ...
# Only last page's tickets survived

# CORRECT - accumulate across pages
all_ticket_data = []  # Defined OUTSIDE the page loop
for page in pdf.pages:
    page_ticket_data = []
    # ... extract tickets ...
    all_ticket_data.extend(page_ticket_data)  # Accumulate
```

### Bug #2: Merged Cells - Multiple Items in One Cell

**Problem:** pdfplumber merges ALL rows into a single cell for complex manifests:
```
SKU cell: "70-11160-0990 70-11162-1010 70-11163-1450..."
DESC cell: "TUBE, 01.000x01.500x...\nTUBE, 01.500x03.000x...\n..."
```

**Solution:** Extract individual SKU/description pairs using regex:
```python
# Find all SKUs
sku_matches = list(re.finditer(r'(\d{2}-\d{5}-\d{4})', sku_cell))

# Find all descriptions
desc_pattern = r'((?:TUBE|ANGLE|FLAT BAR)[,\s\n]*[\d\.\sxX]+)'
desc_matches = list(re.finditer(desc_pattern, desc_cell, re.IGNORECASE))

# Match by position (1st SKU → 1st description)
for i, sku_match in enumerate(sku_matches):
    sku = sku_match.group(1)
    desc = desc_matches[i].group(1).strip() if i < len(desc_matches) else ""
    items.append({"sku": sku, "desc": desc})
```

### APEL Extrusions Manifest Structure

1. **Table extraction is unreliable** - pdfplumber merges cells incorrectly for complex manifests. The main data table often gets split into multiple smaller tables or merged into giant cells.

2. **Hybrid approach works best:**
   - Extract **items (SKU, description)** from table structure
   - Extract **ticket/qty pairs** from text by word position (right side of page, x > 70%)
   - Distribute tickets to items sequentially

3. **Key patterns:**
   - SKU: `\d{2}-\d{5}-\d{4}` (e.g., `70-11242-0850`)
   - Ticket: `^\d{5,6}$` (5-6 digits, but NOT starting with `23` - those are die numbers)
   - Description contains `TUBE` or dimensions like `\d+x\d+`
   - Item numbers: 1-2 digit integers in first column

4. **Filter die numbers:** Die numbers (column 1) are 6 digits starting with `23` (e.g., `230025`). These get picked up by ticket regex - must explicitly filter with `if ticket_num.startswith('23'): continue`

### Debug Strategy

When parsing fails silently (no data extracted):
1. Store debug info in `st.session_state.debug_info`
2. Show debug expander even on failure
3. Log: items found, tickets found, distribution logic
4. Check if data is being lost between loop iterations

### Session State Pattern

```python
# Initialize at module level
if 'debug_info' not in st.session_state:
    st.session_state.debug_info = []

# Store in parsing function
st.session_state.debug_info = debug_info

# Display even on error
if st.session_state.get('debug_info'):
    with st.expander("Debug Info"):
        for line in st.session_state.debug_info:
            st.text(line)
```

### Files

- Main app: `Alcom_Manifest_LabelLive.py`
- Test manifests: `Manifest 2.PDF`, `Manifests Example.PDF`
- Reference screenshots: `Manifest 2.png`, `Output example.png`

### Commands

```bash
# Install
pip install streamlit pdfplumber pandas openpyxl requests

# Run locally
streamlit run Alcom_Manifest_LabelLive.py

# Cloudflare Tunnel (for remote access)
cloudflared tunnel --url http://localhost:8501
```

### Future Improvements

1. **DESCRIPTION shortening** - Currently shows full format. Could shorten to `2X6X2 @85` style
2. **Direct Label LIVE API** - See PHASE 2 section in code
3. **Handle edge cases** - Manifests with different layouts, missing data
