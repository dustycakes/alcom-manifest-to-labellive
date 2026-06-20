# Manifest-to-LabelLIVE — Task List

## Current State: Direct Print Engine Pivot (2026-04-06)

Pivoted from Excel/LABEL LIVE intermediary flow to direct ZPL print from Streamlit.
Uses shared `alcommander-shared/zebra-print` engine (ZPLBuilder with dynamic font scaling).
Existing assets: multi-format parser (Apel, BRT, OCR), 334-SKU description lookup.

**Printer:** Zebra ZD421 (203 DPI), port 9100 TCP
**Templates:** `Zebra-Templates/` — referenced by shared engine's TemplateRegistry

---

## Phase 1: Direct Print Engine

- [x] Scaffold `alcommander-shared/zebra-print/` — ZPLBuilder, TemplateRegistry, PrinterTransport, ZebraPrintService
- [x] Integrate shared engine into Manifest-to-LabelLIVE (import, wire ZebraPrintService)
- [x] Register `extrusion-label-template.prn` as `bunk_label` template spec in shared engine
- [x] Map template fields: SKU (barcode + text), QTY, description — with dynamic scaling constraints
- [x] Test template rendering with static data (preview mode)
- [ ] Integrate "Print Labels" button in Streamlit → calls `print_batch()`
- [ ] Add printer status indicator (`printer_online()`) + preview panel (`preview_label()`)
- [ ] Progress bar for multi-label jobs

## Momentum Parser — text-based (Completed 2026-06-19)

Momentum switched from scanned image PDFs to digital text-layer PDFs, so the
OCR path is obsolete for them. Built a dedicated text-based parser like Apel/BRT.

- [x] Confirm new Momentum PDF has a real text layer (pdfplumber, no OCR)
- [x] New `parsers/momentum_parser.py` (`MomentumParser`, format_id `momentum`)
- [x] SKU read from the labeled `Part:` field — captures non-standard parts
      (e.g. `TRT-TR-21518-10`) that a generic `NN-NNNNN-NNNN` regex would drop
- [x] Comma-tolerant ticket rows (`549011 207 1,188 1,200`); SKU context
      carried across page breaks; multiple manifests per PDF bundled into one
      result (`154719+154720+154721`)
- [x] Registered in `parsers/__init__.py` → auto-appears as "Momentum
      Manufacturing" in the format dropdown
- [x] OCR parser kept as generic scanned-doc fallback
- [x] Validated vs `Manifests/Manifests 2026-06-04.PDF`: 25 bunks / 1,383
      pieces — matches the PDF's printed Grand Totals (3+11+11 tickets)
- [ ] (known, low-pri) OCR parser's old Momentum block still has a comma-weight
      bug; dead for this carrier now, clean up if OCR is ever revisited

## Tires/Axles Labels Tab (Completed)

- [x] Create `tires_axles_lookup.py` module (49 tires, 96 axles)
- [x] Add Tab 3: SKU Lookup + Print Cart workflow
- [x] Multiselect-based SKU picker with tag pills
- [x] Two-mode UI: Browse (70/30 split) → Edit Cart (full width)
- [x] Data editor with persistent state, duplicate row helper
- [x] Bug fixes: schema endpoint 404, auto-save NaN toast, variant param error

## Phase 2: Template Refinement

- [ ] Design label templates in Zebra Designer for Developers
- [ ] Export ZPL and integrate
- [ ] Variable substitution engine
- [ ] Test print quality (barcode readability, text sizing, alignment)

## Phase 3: Polish & Production

- [ ] Printer selection UI
- [ ] Print queue management
- [ ] Print history/log
- [ ] Error handling (offline, paper out, comm errors)
- [ ] Label preview mockup in Streamlit

---

## Completed (Pre-Pivot)

- ✅ Enhanced header design (styled banner with icons)
- ✅ Reorder form modules (format selector above upload)
- ✅ Multi-format parser system (Apel, BRT, OCR)
- ✅ Custom description lookup table (334 SKU mappings)
- ✅ Auto-save edited lookup
- ✅ Text-based extraction (robust across format variations)

---

## Notes

- Run: `streamlit run Alcom_Manifest_LabelLive.py`
- ZPL template: `Zebra-Templates/extrusion-label-template.prn`
- Description lookup: `Manifest Description Conversion.xlsx` (334 SKUs)
