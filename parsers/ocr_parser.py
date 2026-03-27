"""
OCR Manifest Parser

Parses scanned/image-based manifest PDFs using OCR.
Requires pytesseract and pillow for image processing.
"""

import pdfplumber
import pandas as pd
import re
from datetime import datetime
from .base import ManifestParser, ParseResult


# Try to import OCR dependencies
OCR_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    import fitz  # pymupdf for better PDF rendering
    OCR_AVAILABLE = True
except ImportError:
    pass


class OCRParser(ManifestParser):
    """
    Parser for scanned/image-based manifest PDFs.
    
    Uses OCR to extract text from PDFs that don't have extractable text.
    Requires: pytesseract, pillow, pymupdf
    """
    
    @property
    def format_name(self) -> str:
        return "OCR (Scanned Documents)"
    
    @property
    def format_id(self) -> str:
        return "ocr"
    
    def parse(self, pdf_file) -> ParseResult:
        """Parse manifest PDF using OCR."""
        debug_info = []

        if not OCR_AVAILABLE:
            return ParseResult(
                df=pd.DataFrame(),
                manifest_number="",
                debug_info=[
                    "OCR dependencies not available.",
                    "Install with: pip install pytesseract pillow pymupdf",
                    "Also requires Tesseract OCR installed on system."
                ],
                parser_type=self.format_id
            )

        all_text = ""
        manifest_number = ""
        
        # Read PDF bytes
        pdf_bytes = pdf_file.read()
        
        # Use pymupdf to render pages as images from bytes
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        debug_info.append(f"Processing {len(doc)} pages with OCR")

        for page_num, page in enumerate(doc, 1):
            # Render page as image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img_data = pix.tobytes("png")

            # OCR the image
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(img_data))
            page_text = pytesseract.image_to_string(img)

            if page_text:
                all_text += page_text + "\n"
                debug_info.append(f"Page {page_num}: OCR extracted {len(page_text)} chars")

        doc.close()
        
        # Extract manifest number
        if all_text.strip():
            manifest_number = self._extract_manifest_number(all_text)
        
        # Try to extract SKU/ticket data using Apel parser logic as fallback
        # This assumes most manifests follow similar patterns
        bunks = self._extract_data_from_ocr_text(all_text)
        
        df = pd.DataFrame(bunks)
        
        if not df.empty:
            debug_info.append(f"Total bunks: {len(bunks)}")
            debug_info.append(f"Unique SKUs: {df['SKU'].nunique()}")
        
        return ParseResult(
            df=df,
            manifest_number=manifest_number,
            debug_info=debug_info,
            parser_type=self.format_id
        )
    
    def can_parse(self, pdf_file) -> bool:
        """Check if PDF needs OCR (no extractable text)."""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                if not pdf.pages:
                    return False
                
                # Check if any page has extractable text
                for page in pdf.pages[:3]:  # Check first 3 pages
                    text = page.extract_text() or ""
                    if text.strip() and len(text) > 100:
                        return False  # Has text, doesn't need OCR
                
                # No text found - likely scanned
                return True
        except Exception:
            return False
    
    def _extract_manifest_number(self, text: str) -> str:
        """Extract manifest number from OCR text."""
        patterns = [
            r'MANIFEST\s*NUMBER.*?(\d+)',
            r'MANIFEST\s*NO\.?\s*[:\-]?\s*(\d+)',
            r'Manifest\s*#?\s*[:\-]?\s*([A-Z0-9\-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def _extract_data_from_ocr_text(self, text: str) -> list[dict]:
        """
        Extract SKU/ticket/qty data from OCR text.

        Handles multiple manifest formats:
        - Apel: ticket (64/65xxxx) + qty
        - BRT: ticket (1xxxxxx) + qty + weight
        - Momentum Bill of Lading: ticket (6-digit) + pieces + pounds
        """
        bunks = []
        lines = text.split('\n')
        current_sku = None

        for line in lines:
            # Track SKU context
            sku_match = re.search(r'(\d{2}-\d{5}-\d{4})', line)
            if sku_match:
                current_sku = sku_match.group(1)

            # Momentum Bill of Lading format:
            # "539735 24 537 549" <- ticket, pieces, net lbs, gross lbs
            # Look for: 6-digit ticket followed by 2-4 digit quantity
            momentum_match = re.findall(r'\b(\d{6})\s+(\d{2,4})\s+\d{2,5}\s+\d{2,5}\b', line)
            for ticket, qty in momentum_match:
                # Skip if it looks like a date or other number
                if ticket.startswith('20') or ticket.startswith('03'):
                    continue
                if current_sku and 10 <= int(qty) <= 500:
                    bunks.append({
                        "SKU": current_sku,
                        "QTY_pieces": int(qty),
                        "TICKET": ticket
                    })

            # Apel-style tickets (64/65xxxx)
            apel_tickets = re.findall(r'\b(6[45]\d{4})\b', line)
            for ticket in apel_tickets:
                # Look for quantity nearby
                qty_match = re.search(r'\b(\d{2,4})\b', line)
                if qty_match and current_sku:
                    qty = int(qty_match.group(1))
                    if 10 < qty < 500:
                        bunks.append({
                            "SKU": current_sku,
                            "QTY_pieces": qty,
                            "TICKET": ticket
                        })

            # BRT-style tickets (1xxxxxx)
            brt_tickets = re.findall(r'\b(1\d{6})\b', line)
            for ticket in brt_tickets:
                qty_match = re.search(r'\b(\d{2,4})\b', line)
                if qty_match and current_sku:
                    qty = int(qty_match.group(1))
                    if 10 < qty < 500:
                        bunks.append({
                            "SKU": current_sku,
                            "QTY_pieces": qty,
                            "TICKET": ticket
                        })

        return bunks
