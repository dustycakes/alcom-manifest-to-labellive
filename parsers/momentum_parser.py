"""
Momentum Manufacturing Group Manifest Parser

Parses Momentum (Engineered Extrusions) manifest PDFs using text-based
extraction. As of 2026-06 Momentum sends digital text-layer PDFs; previously
they were scanned images handled by the OCR parser. This parser reads the
real text layer directly (like the Apel/BRT parsers) — no OCR needed.

Format notes (see Manifests/Manifests 2026-06-04.PDF for a reference):

  - A single PDF may bundle MULTIPLE manifests (e.g. 154719, 154720, 154721),
    each with its own PO / Sales Order, each spanning one or more pages with
    repeated page headers and "** CONTINUATION **" markers. We extract every
    bunk across all of them and label the batch with the combined manifest
    numbers (e.g. "154719+154720+154721").

  - Each manifest is split into Items. An Item block looks like:

        Length Descr: <description>          Item: <N>
        <len>"  Section: <section#>  Part: <PART#>  Alloy/Temp: <alloy>
        Ticket Pieces Net Pounds Gross
        <ticket> <pieces> <net> <gross>      <- one row per bunk
        Item Total <pieces> <net> <gross>

  - SKU is taken straight from the labeled "Part:" field. Most parts are the
    standard NN-NNNNN-NNNN form, but some are non-standard (e.g.
    TRT-TR-21518-10), so we never rely on a generic SKU regex that would drop
    them — the explicit Part: label is authoritative.

  - Tickets are 6-digit numbers. Section numbers are ALSO 6-digit, so a line is
    only treated as a bunk when it matches the full "<ticket> <pieces> <net>
    <gross>" shape. Net/gross weights may carry thousands-commas (e.g. 1,188).
"""

import re
from datetime import datetime

import pdfplumber
import pandas as pd

from .base import ManifestParser, ParseResult


class MomentumParser(ManifestParser):
    """Parser for Momentum Manufacturing Group manifest PDFs (text-based)."""

    # SKU comes straight from the "Part:" label — handles non-standard parts.
    _PART_RE = re.compile(r"Part:\s*([A-Za-z0-9][A-Za-z0-9\-]+)")
    # A bunk row: 6-digit ticket, pieces, net, gross. Weights may have commas.
    _ROW_RE = re.compile(r"^(\d{6})\s+(\d{1,4})\s+[\d,]+\s+[\d,]+$")
    # Manifest number from the repeated page header ("Manifest 154719 Ship Date").
    _MANIFEST_RE = re.compile(r"\bManifest\s+(\d{4,})", re.IGNORECASE)

    @property
    def format_name(self) -> str:
        return "Momentum Manufacturing"

    @property
    def format_id(self) -> str:
        return "momentum"

    def parse(self, pdf_file) -> ParseResult:
        """Parse a Momentum manifest PDF using text extraction."""
        debug_info = []

        # Concatenate every page so SKU context flows across page breaks
        # (an Item's ticket rows can continue onto the next page).
        all_text = ""
        with pdfplumber.open(pdf_file) as pdf:
            debug_info.append(f"Processing {len(pdf.pages)} pages")
            for page in pdf.pages:
                text = page.extract_text() or ""
                all_text += text + "\n"

        # A single PDF may bundle several manifests — collect them in order,
        # de-duplicated (the header repeats on every page).
        manifest_numbers = []
        for match in self._MANIFEST_RE.finditer(all_text):
            num = match.group(1)
            if num not in manifest_numbers:
                manifest_numbers.append(num)
        manifest_number = "+".join(manifest_numbers)
        debug_info.append(f"Manifests found: {manifest_number or '(none)'}")

        bunks = []
        current_sku = None

        for raw_line in all_text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            # Update SKU context whenever we hit a "Part:" line. This line never
            # also contains a bunk row, so move on once we've captured the SKU.
            part_match = self._PART_RE.search(line)
            if part_match:
                current_sku = part_match.group(1).strip()
                continue

            # A bunk row: <ticket> <pieces> <net> <gross>.
            row_match = self._ROW_RE.match(line)
            if row_match and current_sku:
                bunks.append({
                    "SKU": current_sku,
                    "QTY_pieces": int(row_match.group(2)),
                    "TICKET": row_match.group(1),
                })

        df = pd.DataFrame(bunks)

        if not df.empty:
            debug_info.append(f"Total bunks: {len(bunks)}")
            debug_info.append(f"Unique SKUs: {df['SKU'].nunique()}")
        else:
            debug_info.append("No bunks extracted — check that this is a Momentum manifest.")

        # Fall back to a timestamp if no manifest number was found (parity with
        # the Apel/BRT parsers, keeps the Excel filename non-empty).
        if not manifest_number:
            manifest_number = datetime.now().strftime("%Y%m%d_%H%M%S")

        return ParseResult(
            df=df,
            manifest_number=manifest_number,
            debug_info=debug_info,
            parser_type=self.format_id,
        )

    def can_parse(self, pdf_file) -> bool:
        """Check if the PDF appears to be a Momentum manifest."""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                if not pdf.pages:
                    return False
                text = (pdf.pages[0].extract_text() or "").lower()
                return "momentum" in text or "engineered extrusions" in text
        except Exception:
            return False
