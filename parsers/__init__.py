"""
Manifest Parsers Package

Provides unified interface for parsing different manifest formats.
"""

from .base import ManifestParser, ParseResult
from .apel_parser import ApelParser
from .brt_parser import BRTParser
from .ocr_parser import OCRParser

# Registry of available parsers
PARSERS = {
    "apel": ApelParser,
    "brt": BRTParser,
    "ocr": OCRParser,
}


def get_parser(format_type: str) -> ManifestParser:
    """Get parser instance by format type."""
    if format_type not in PARSERS:
        raise ValueError(f"Unknown manifest format: {format_type}")
    return PARSERS[format_type]()


def get_available_formats() -> list[str]:
    """Return list of available manifest format names."""
    return list(PARSERS.keys())
