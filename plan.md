# Development Plan

> This document serves as a living To-Do list and agenda for the Manifest → Label LIVE project.

---

## 🔄 MAJOR PIVOT — 2026-04-06

**Direction:** Print directly from the Streamlit app to the Zebra ZD421 printer, bypassing the Excel intermediary.

**Current Flow (OLD):**
```
PDF Manifest → Streamlit (parse) → Excel download → Label LIVE software → Zebra ZD421
```

**New Flow (TARGET):**
```
PDF Manifest → Streamlit (parse + description lookup) → Zebra ZD421 (direct print)
```

**Approach:**
- **Zebra Designer for Developers** — used as the label template generator (produces `.prn` / `.zpl` files)
- **Python print engine** — sends ZPL/PRN directly to the Zebra ZD421 printer from Streamlit
- **Existing ZPL template:** `Zebra-Templates/extrusion-label-template.prn` (already exists, needs variable mapping)

---

## Phase 1: Direct Print Engine

### Tasks

- [ ] **Research Zebra ZD421 print methods from Python**
  - Raw ZPL over network (port 9100)
  - USB via `pyusb` or `win32print`
  - Zebra Browser Print API (JavaScript-based, may not fit Streamlit)
  - Zebra Link-OS SDK (Python bindings?)
- [ ] **Determine deployment environment** (Windows? Linux? Network-connected printer?)
- [ ] **Select print strategy** based on environment

- [ ] **Map existing ZPL template variables**
  - `FN1"VARSKU"` → SKU field
  - `FN2"VARQTY"` → QTY field
  - `FN3"VARMATERIALNAME"` → Custom description
  - Understand field positioning, sizing, barcode format
- [ ] **Test template with static data** — send a sample label to printer

- [ ] **Build Python print function**
  - Input: list of `{sku, qty, description, labels_to_print}`
  - Output: ZPL stream sent to printer
  - Support: preview (ZPL text) + print modes
  - Handle: multiple copies per bunk

- [ ] **Integrate into Streamlit UI**
  - Replace "Download Excel for Label LIVE" button with "Print Labels" button
  - Add print preview panel (show ZPL or rendered label mockup)
  - Add printer status indicator
  - Progress bar for multi-label jobs

---

## Phase 2: Template Refinement

- [ ] **Design label templates in Zebra Designer for Developers**
  - Bunk label (3" x 5" pouch) — SKU, description, qty, barcode
  - Consider multiple label sizes if needed
- [ ] **Export ZPL from Zebra Designer** and integrate
- [ ] **Variable substitution engine** — replace `^FN` fields with actual data
- [ ] **Test print quality** — barcode readability, text sizing, alignment

---

## Phase 3: Polish & Production

- [ ] **Printer selection UI** — if multiple Zebra printers on network
- [ ] **Print queue management** — pause, resume, cancel
- [ ] **Print history/log** — audit trail of what was printed when
- [ ] **Error handling** — printer offline, paper out, communication errors
- [ ] **Label preview** — visual mockup in Streamlit before printing

---

## Completed (Pre-Pivot)

- **Enhance header design** - Styled banner with icons and accent colors
- **Reorder form modules** - Manifest Format selector above Upload
- **Multi-format parser system** — Apel, BRT, OCR (Momentum) parsers
- **Custom description lookup table** — 334 SKU mappings
- **Auto-save edited lookup** — no more data loss on filtered saves
- **Text-based extraction** — more robust than table extraction across formats

## Completed (Tires/Axles Tab — 2026-04-06)

- **Tires/Axles Labels Tab (Tab 3)** — SKU Lookup + Print Cart workflow
- **Tires/Axles Lookup Module** — 49 tires (60-), 96 axles (65-) from `Tires-Axles.xlsx`
- **Multiselect SKU Picker** — Built-in search, tag pills, "[Select all]" bulk add
- **Two-Mode UI** — Browse (70/30 split) → Edit Cart (full width)
- **Data Editor** — Persistent state, duplicate row helper, sync on every interaction
- **ZPLBuilder Integration** — Shared engine with template registration, preview mode
- **Bug Fixes** — Schema endpoint 404, auto-save NaN toast, `variant` param error

---

## Future Considerations

- Keep Excel export as fallback option?
- Cloud-based print relay (if printer not on same network)?
- Mobile-friendly Streamlit for floor-side printing?
- Label design versioning?
