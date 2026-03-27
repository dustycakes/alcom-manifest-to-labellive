"""
Base Manifest Parser

Abstract base class defining the interface for all manifest parsers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import pandas as pd


@dataclass
class ParseResult:
    """Result of parsing a manifest PDF."""
    
    # DataFrame with columns: SKU, QTY_pieces, TICKET
    df: pd.DataFrame
    
    # Manifest metadata
    manifest_number: str = ""
    
    # Debug information for troubleshooting
    debug_info: list[str] = field(default_factory=list)
    
    # Parser that processed this (for debugging)
    parser_type: str = ""
    
    @property
    def success(self) -> bool:
        """True if parsing produced results."""
        return not self.df.empty
    
    @property
    def unique_skus(self) -> int:
        """Number of unique SKUs in result."""
        if self.df.empty:
            return 0
        return self.df["SKU"].nunique()
    
    @property
    def total_bunks(self) -> int:
        """Total number of bunks (rows) in result."""
        return len(self.df)
    
    @property
    def total_pieces(self) -> int:
        """Total quantity of pieces."""
        if self.df.empty:
            return 0
        return int(self.df["QTY_pieces"].sum())


class ManifestParser(ABC):
    """
    Abstract base class for manifest parsers.
    
    Each manifest format (Apel, BRT, OCR, etc.) implements this interface.
    """
    
    @property
    @abstractmethod
    def format_name(self) -> str:
        """Human-readable name for this format (e.g., 'Apel Extrusions')."""
        pass
    
    @property
    @abstractmethod
    def format_id(self) -> str:
        """Short identifier for this format (e.g., 'apel')."""
        pass
    
    @abstractmethod
    def parse(self, pdf_file) -> ParseResult:
        """
        Parse a manifest PDF file.
        
        Args:
            pdf_file: File-like object containing PDF data
            
        Returns:
            ParseResult with extracted data
        """
        pass
    
    def can_parse(self, pdf_file) -> bool:
        """
        Check if this parser can handle the given PDF.
        
        Override in subclasses to implement format detection.
        Default implementation returns False (must be explicit).
        
        Args:
            pdf_file: File-like object containing PDF data
            
        Returns:
            True if this parser believes it can handle the PDF
        """
        return False
