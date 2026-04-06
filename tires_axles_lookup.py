"""
tires_axles_lookup.py — SKU lookup for Tires and Axles label generation.

Loads from Tires-Axles.xlsx (2 sheets: Tires, Axles).
Provides filtered search and SKU details for the label cart workflow.
"""

import pandas as pd
from pathlib import Path


class TiresAxlesLookup:
    """Loads and queries the Tires and Axles SKU reference data."""

    def __init__(self, filepath: str | Path):
        self._filepath = Path(filepath)
        self._tires: pd.DataFrame | None = None
        self._axles: pd.DataFrame | None = None
        self._load()

    def _load(self):
        """Load both sheets from the Excel file."""
        xl = pd.ExcelFile(str(self._filepath))
        self._tires = pd.read_excel(xl, sheet_name="Tires")
        self._axles = pd.read_excel(xl, sheet_name="Axles")

        # Normalize column names
        for df in [self._tires, self._axles]:
            df.columns = df.columns.str.strip()
            # Ensure Item column is string
            df["Item"] = df["Item"].astype(str).str.strip()
            # Fill null descriptions
            df["Description"] = df["Description"].fillna("")

    def get_tires(self) -> pd.DataFrame:
        """Return all tire SKUs."""
        return self._tires.copy()

    def get_axles(self) -> pd.DataFrame:
        """Return all axle SKUs."""
        return self._axles.copy()

    def search(self, category: str, query: str) -> pd.DataFrame:
        """
        Search SKUs by category (tires/axles) and query string.
        Searches both Item (SKU) and Description columns.
        Returns matching rows.
        """
        df = self.get_axles() if category == "axles" else self.get_tires()
        if not query:
            return df

        q = query.lower()
        mask = (
            df["Item"].str.lower().str.contains(q, na=False)
            | df["Description"].str.lower().str.contains(q, na=False)
        )
        return df[mask]

    def get_description(self, category: str, sku: str) -> str:
        """Get description for a specific SKU."""
        df = self.get_axles() if category == "axles" else self.get_tires()
        match = df[df["Item"] == sku]
        if len(match) > 0:
            return str(match.iloc[0]["Description"])
        return ""
