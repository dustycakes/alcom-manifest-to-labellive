"""
BRT Extrusions Manifest Parser

Parses BRT manifest PDFs using text-based extraction.
BRT manifests have a different layout than Apel:
- Header: "SHIPPING MANIFEST"
- Tickets are 7-digit numbers (1xxxxxx)
- Text format: ticket qty weight (e.g., "1373341 97 407")
"""

import pdfplumber
import pandas as pd
import re
from datetime import datetime
from .base import ManifestParser, ParseResult


class BRTParser(ManifestParser):
    """Parser for BRT Extrusions manifest PDFs."""
    
    @property
    def format_name(self) -> str:
        return "BRT Extrusions"
    
    @property
    def format_id(self) -> str:
        return "brt"
    
    def parse(self, pdf_file) -> ParseResult:
        """Parse BRT manifest PDF using text extraction."""
        debug_info = []
        all_bunks = []
        manifest_numbers = []
        
        with pdfplumber.open(pdf_file) as pdf:
            debug_info.append(f"Processing {len(pdf.pages)} pages")
            
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                
                # Extract manifest number from page
                manifest_match = re.search(r'(\d{6})\s+\d{1,2}/\d{1,2}/\d{2,4}', text)
                if manifest_match:
                    manifest_numbers.append(manifest_match.group(1))
                
                # Parse page text for SKU/ticket/qty
                page_bunks = self._parse_page_text(text, page_num)
                all_bunks.extend(page_bunks)
                
                debug_info.append(f"Page {page_num}: found {len(page_bunks)} bunks")
        
        df = pd.DataFrame(all_bunks)
        
        # Use first manifest number found
        manifest_number = manifest_numbers[0] if manifest_numbers else ""
        
        # Debug info
        if not df.empty:
            debug_info.append(f"Total bunks: {len(all_bunks)}")
            debug_info.append(f"Unique SKUs: {df['SKU'].nunique()}")
        
        return ParseResult(
            df=df,
            manifest_number=manifest_number,
            debug_info=debug_info,
            parser_type=self.format_id
        )
    
    def can_parse(self, pdf_file) -> bool:
        """Check if PDF appears to be a BRT manifest."""
        try:
            with pdfplumber.open(pdf_file) as pdf:
                if not pdf.pages:
                    return False
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""
                
                has_shipping_manifest = 'SHIPPING MANIFEST' in text.upper()
                has_brt_url = 'brtextrusions.com' in text.lower()
                
                return has_shipping_manifest or has_brt_url
        except Exception:
            return False
    
    def _parse_page_text(self, text: str, page_num: int) -> list[dict]:
        """
        Parse page text to extract SKU/ticket/qty triplets.
        
        BRT text format has tickets with qty/weight nearby:
        "1373341 97 407" <- ticket, qty, weight
        
        SKUs appear in lines above ticket data.
        """
        bunks = []
        lines = text.split('\n')
        current_sku = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Track current SKU context
            sku_match = re.search(r'(\d{2}-\d{5}-\d{4})', line)
            if sku_match:
                current_sku = sku_match.group(1)
            
            # Look for ticket/qty/weight pattern: 7-digit ticket followed by qty and weight
            # Pattern: "1373341 97 407" or "1374652 32 68" or "1374256 20 1,465" (weight may have comma)
            matches = re.findall(r'\b(1\d{6})\s+(\d{2,3})\s+([\d,]{2,5})\b', line)
            
            for match in matches:
                ticket = match[0]
                qty = int(match[1])
                # weight = match[2]  # Not needed for our output
                
                if current_sku:
                    bunks.append({
                        "SKU": current_sku,
                        "QTY_pieces": qty,
                        "TICKET": ticket
                    })
        
        return bunks
    
    def _extract_manifest_number(self, text: str) -> str:
        """Extract manifest number from text."""
        patterns = [
            r'MANIFEST\s*NUMBER.*?(\d+)',
            r'MANIFEST\s*NO\.?\s*[:\-]?\s*(\d+)',
            r'(\d{6})\s+\d{1,2}/\d{1,2}/\d{2,4}',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return datetime.now().strftime("%Y%m%d_%H%M%S")
