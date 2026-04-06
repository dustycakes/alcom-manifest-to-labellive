# Lessons Learned - Alcom Manifest to Label LIVE

## Date: 2026-04-06

### Tires/Axles Label Generator — UI Patterns and Streamlit Gotchas

**1. `st.data_editor` state persistence is fragile**
- **Problem:** Editing cell 1, then hitting Enter in cell 2 wiped cell 1's edit. The editor rebuilt from session state on every rerun, losing in-progress edits.
- **Solution:** Persist the editor's DataFrame in `st.session_state.ta_cart_df` with a version counter. Only rebuild when cart length changes. Use `on_change` callback to sync edits immediately.
- **Rule:** Never rebuild `st.data_editor` data from source on every render. Persist in session state with a change detector.

**2. Avoid external UI controls that mutate `st.data_editor` state**
- **Problem:** "Add Duplicate" button modified the cart list behind the scenes, causing the data_editor to rebuild and wipe user edits. Race conditions between button clicks and editor internal state.
- **Solution:** Remove external mutation buttons entirely. Let the editor's built-in `+` row addition handle new rows. Make SKU column editable so users can type directly.
- **Rule:** Don't mix external mutation controls with `st.data_editor`. Let the editor own its data.

**3. `st.button(variant="secondary")` not supported in all Streamlit versions**
- **Problem:** `TypeError: ButtonMixin.button() got an unexpected keyword argument 'variant'` — this parameter was added in Streamlit 1.42.0.
- **Solution:** Remove `variant` argument. Use default button styling.
- **Rule:** Check Streamlit version compatibility before using newer UI parameters.

**4. `st.data_editor` `num_rows="dynamic"` is the native "add row" solution**
- The `+` button at the bottom of the table adds blank rows. Combined with an editable SKU column, users can add duplicates by typing the same SKU. No custom duplicate button needed.

**5. Two-mode workflow pattern (Browse → Edit)**
- Default mode: split layout (70/30) with SKU lookup dominating
- Edit mode: full-width cart editor, lookup hidden
- Toggle via `st.session_state.ta_mode` with explicit button
- Clear Cart resets mode to Browse automatically
- **Rule:** Use session state mode flags for multi-phase workflows. Always provide an explicit "back" button.

**6. Multiselect as primary selection interface**
- Streamlit's `st.multiselect` has built-in search + tag pills with × buttons
- Far superior to custom checkbox lists or HTML-rendered rows
- "[Select all]" as first option for bulk operations
- **Rule:** Use `st.multiselect` for any multi-item selection workflow. It handles search, tags, and deselection natively.

**7. Auto-save NaN bug in data editor**
- **Problem:** Empty rows in `st.data_editor` caused "✓ Added nan" toast spam. `str(row['GENIUS #'])` converts NaN to the string "nan".
- **Solution:** Check `pd.isna(sku_val)` and filter string "nan" before processing.
- **Rule:** Always validate for NaN before stringifying pandas values.

**8. `/api/inventory.schema` vs `/api/inventory.schema` (slash vs dot)**
- **Problem:** 404 on schema endpoint. Code called `/api/inventory.schema` but the API expects `/api/inventory/schema`.
- **Rule:** Always test API endpoints with curl before hardcoding paths.

### ZPLBuilder Shared Engine Integration

**9. Shared library import path**
- Use `sys.path.insert(0, "../alcommander-shared/zebra-print")` for cross-project imports
- Import inside function body (not module top) to avoid breaking when path isn't available
- Wrap in try/except with user-friendly error message

**10. Template registration requires explicit field definitions**
- ZPLBuilder needs `TemplateField` objects with position, scaling constraints, and rotation
- Coordinates are in dots at 203 DPI (ZD421)
- `max_lines > 1` enables `^FB` wrapping
- **Rule:** Document template specs alongside the .prn file they were derived from.

## Date: 2026-03-28

### UI Enhancements - Header and Form Layout

**Goal:** Improve visual hierarchy and user flow with minimal custom CSS.

**Changes:**
1. **Header redesign** - Replaced `st.title()` + separator with custom banner:
   - Large text (2.5rem title, 2rem flow) using inline styles only
   - Package icon (📦) represents materials being processed
   - Visual flow: "Manifest → Label LIVE ✓" with green accent
   - ~40 lines of CSS → ~6 lines of inline styles

2. **Form reordering** - Moved "Manifest Format" selector above "Upload":
   - Logical flow: select format first, then upload matching file
   - Matches the numbered instructions in sidebar

3. **Icon updates**:
   - Total Pieces: 🔧 (wrench) → 📋 (clipboard) for inventory/counting context
   - Header: Removed printer emoji, kept package (📦) for simplicity

4. **Removed debug expander** - Cleaned up UI for production use (debug info still collected in session_state if needed)

**Design Principle:** Use Streamlit's native theming via CSS variables where possible, minimal inline styles only for sizing and accent colors.

**Files:**
- `Alcom_Manifest_LabelLive.py` - `render_header()` function, form order
- `plan.md` - Updated with completed tasks

---

## Date: 2026-03-27

### Architecture: Multi-Format Parser System

**Problem:** Need to support multiple manifest formats (Apel, BRT, Momentum/OCR, future suppliers) without code becoming unmaintainable.

**Solution:** Abstract base class + registry pattern with explicit format selection (Option B → Option C path).

**Design:**
```
parsers/
  ├── base.py          # ManifestParser ABC, ParseResult dataclass
  ├── apel_parser.py   # Apel Extrusions (existing logic)
  ├── brt_parser.py    # BRT Extrusions (new)
  └── ocr_parser.py    # Scanned documents (future: pytesseract)

Alcom_Manifest_LabelLive.py
  └─ UI: selectbox("Manifest Format") → parser.parse()
```

**Key Decisions:**
1. **Option B (User Selects Format)** for v1 - explicit, debuggable, no fragile auto-detection
2. **Path to Option C** - each parser has `can_parse()` method for future auto-detect
3. **OCR ready** - OCRParser stub included, can enable when tesseract installed
4. **Easy extension** - Add new parser: create class, register in `parsers/__init__.py`

**BRT Format Differences:**
- Header: "SHIPPING MANIFEST" + brtextrusions.com
- Tickets: 7-digit (1xxxxxx), not 64/65xxxx like Apel
- Text format: `ticket qty weight` (e.g., "1373341 97 407")
- Multiple SKUs per page, text-based extraction works best

**BRT Parser Bug Fixes:**
1. **Table extraction unreliable** - pdfplumber merges rows incorrectly → switched to text-based extraction
2. **Weight with commas** - Pattern `1,465` wasn't matching `\d{2,4}` → changed to `[\d,]{2,5}`
3. **2-digit weights** - Weight `68` wasn't matching `\d{3,4}` → changed to `\d{2,4}`
4. **SKU context tracking** - Tickets appear on lines without SKU → track context from previous line

**Results:**
| Metric | Expected | Actual |
|--------|----------|--------|
| BRT 1.PDF bunks | 64 | 64 ✓ |
| BRT 1.PDF SKUs | 16 | 16 ✓ |
| Order preserved | Yes | Yes ✓ |

**Files:**
- `parsers/` - New package with parser architecture
- `Alcom_Manifest_LabelLive.py` - Added format selector dropdown

### OCR Parser - Momentum Bill of Lading

**Format:** Scanned Bill of Lading documents (image-based PDFs)
- Requires: `pytesseract`, `pillow`, `pymupdf` + system `tesseract`
- Renders PDF pages as images, runs OCR to extract text

**Momentum Format:**
- Document type: "STRAIGHT BILL OF LADING - SHORT FORM"
- Tickets: 6-digit (e.g., `539735`)
- Pattern: `ticket pieces net_lbs gross_lbs` (e.g., "539735 24 537 549")
- SKUs: Same format as Apel/BRT (`XX-XXXXX-XXXX`)

**OCR Parser Design:**
- Isolated from Apel/BRT parsers - changes don't affect them
- Supports multiple formats: Apel, BRT, Momentum
- Momentum detection: 6-digit ticket + 3 numbers pattern

**Results:**
| Metric | Value |
|--------|-------|
| Momentum bunks | 12 |
| Momentum SKUs | 5 |
| Manifest number | 153082 |

**Files:**
- `parsers/ocr_parser.py` - OCR parser with Momentum support
- `requirements.txt` - Added optional OCR dependencies (commented)

### OCR Bug Fix: Streamlit UploadedFile BytesIO

**Problem:** OCR parser returned "No data extracted" in Streamlit UI, but worked in direct Python tests.

**Root Cause:** OCR parser used `pdf_file.name` to get file path for pymupdf. Streamlit's `UploadedFile` is a BytesIO wrapper without a real file path, so `pdf_path` was `None` and pymupdf couldn't open it.

```python
# BUGGY CODE
pdf_path = pdf_file.name if hasattr(pdf_file, 'name') else None
if pdf_path:
    doc = fitz.open(pdf_path)  # Works with file path
else:
    # Fallback to pdfplumber - useless for scanned PDFs!
```

**Fix:** Read PDF bytes directly and use pymupdf's stream API:

```python
# FIXED CODE
pdf_bytes = pdf_file.read()
doc = fitz.open(stream=pdf_bytes, filetype="pdf")  # Works with BytesIO
```

**Files:**
- `parsers/ocr_parser.py` - Fixed to handle BytesIO uploaded files

---

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
