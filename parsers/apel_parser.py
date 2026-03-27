"""
Apel Extrusions Manifest Parser

Parses Apel manifest PDFs using text-based extraction.
Handles Apel 1, 2, and 3 formats.
"""

import pdfplumber
import pandas as pd
import re
from datetime import datetime
from .base import ManifestParser, ParseResult


class ApelParser(ManifestParser):
    """Parser for Apel Extrusions manifest PDFs."""
    
    @property
    def format_name(self) -> str:
        return "Apel Extrusions"
    
    @property
    def format_id(self) -> str:
        return "apel"
    
    def parse(self, pdf_file) -> ParseResult:
        """Parse Apel manifest PDF."""
        debug_info = []
        
        # Read entire PDF text
        all_text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"
        
        # Extract manifest number
        manifest_number = self._extract_manifest_number(all_text)
        
        # Extract tickets using text-based method
        tickets = self._extract_tickets_from_text(all_text)
        debug_info.append(f"Extracted {len(tickets)} tickets from text")
        
        # Create bunks in order (preserve manifest order)
        bunks = []
        for ticket, qty, sku_context in tickets:
            if sku_context:
                bunks.append({
                    "SKU": sku_context,
                    "QTY_pieces": qty,
                    "TICKET": ticket
                })
        
        df = pd.DataFrame(bunks)
        
        # Debug info
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
        """Check if PDF appears to be an Apel manifest."""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                if not pdf.pages:
                    return False
                # Check first page for Apel indicators
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""
                
                # Apel manifests have tickets starting with 64 or 65
                apel_tickets = len(re.findall(r'\b64\d{4}\b|\b65\d{4}\b', text))
                
                # Also check for typical Apel header patterns
                has_manifest = 'MANIFEST' in text.upper()
                
                return has_manifest and apel_tickets > 0
        except Exception:
            return False
    
    def _extract_manifest_number(self, text: str) -> str:
        """Extract manifest number from PDF text."""
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
    
    def _extract_tickets_from_text(self, text: str) -> list[tuple[str, int, str]]:
        """
        Extract ticket/qty pairs from text.
        Pattern: 647265 18 428  <- ticket, qty, weight
        """
        tickets = []
        lines = text.split('\n')
        current_sku = None
        
        for line in lines:
            # Track SKU context
            sku_match = re.search(r'(\d{2}-\d{5}-\d{4})', line)
            if sku_match:
                current_sku = sku_match.group(1)
            
            words = line.split()
            for i, word in enumerate(words):
                # Find tickets (6 digits starting with 64 or 65)
                ticket_match = re.match(r'^(64|65)\d{4}$', word)
                if ticket_match:
                    ticket_num = word
                    
                    # Skip die numbers (start with 23)
                    if ticket_num.startswith('23'):
                        continue
                    
                    # Look for quantity (next number)
                    for j in range(i + 1, min(i + 3, len(words))):
                        qty_word = words[j].replace(',', '')
                        qty_match = re.match(r'^(\d+)$', qty_word)
                        if qty_match:
                            qty_num = int(qty_match.group(1))
                            if 0 < qty_num < 1000:
                                tickets.append((ticket_num, qty_num, current_sku))
                                break
        
        return tickets
