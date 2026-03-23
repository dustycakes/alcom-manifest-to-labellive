# Lessons Learned - Alcom Manifest to Label LIVE

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
