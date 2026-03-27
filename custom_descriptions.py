"""
Custom Description Lookup Module

Manages the mapping between SKUs (GENIUS #) and custom descriptions.
Loads from and saves to Excel file.
"""

import pandas as pd
import os
from typing import Optional

DEFAULT_FILE = "Manifest Description Conversion.xlsx"


class CustomDescriptionLookup:
    """Lookup table for custom descriptions by SKU."""
    
    def __init__(self, filepath: str = DEFAULT_FILE):
        self.filepath = filepath
        self.df: Optional[pd.DataFrame] = None
        self._load()
    
    def _load(self):
        """Load the lookup table from Excel file."""
        if os.path.exists(self.filepath):
            self.df = pd.read_excel(self.filepath)
            # Normalize column names
            self.df.columns = [col.strip().upper() for col in self.df.columns]
            # Ensure GENIUS # column is string for matching
            if 'GENIUS #' in self.df.columns:
                self.df['GENIUS #'] = self.df['GENIUS #'].astype(str)
        else:
            # Create empty dataframe with expected columns
            self.df = pd.DataFrame(columns=['GENIUS #', 'CUSTOM DESCRIPTION', 'DESCRIPTION'])
    
    def save(self):
        """Save the lookup table to Excel file."""
        self.df.to_excel(self.filepath, index=False)
    
    def get_custom_description(self, sku: str) -> Optional[str]:
        """
        Get custom description for a SKU.
        
        Args:
            sku: The SKU to look up (e.g., "70-11160-0990")
            
        Returns:
            Custom description if found, None otherwise
        """
        if self.df is None or 'GENIUS #' not in self.df.columns:
            return None
        
        # Normalize SKU for matching
        sku = str(sku).strip()
        
        # Look up in dataframe
        match = self.df[self.df['GENIUS #'] == sku]
        if len(match) > 0:
            custom_desc = match.iloc[0]['CUSTOM DESCRIPTION']
            # Return None if custom description is NaN/empty
            if pd.isna(custom_desc) or str(custom_desc).strip() == '':
                return None
            return str(custom_desc).strip()
        return None
    
    def get_all_descriptions(self) -> pd.DataFrame:
        """Return the full lookup table as a DataFrame."""
        return self.df.copy()
    
    def add_or_update(self, sku: str, custom_description: str, original_description: str = ""):
        """
        Add or update a SKU entry.
        
        Args:
            sku: The SKU (GENIUS #)
            custom_description: The custom description to use
            original_description: Optional original description from manifest
        """
        sku = str(sku).strip()
        
        # Check if SKU exists
        existing = self.df[self.df['GENIUS #'] == sku]
        
        if len(existing) > 0:
            # Update existing
            idx = existing.index[0]
            self.df.at[idx, 'CUSTOM DESCRIPTION'] = custom_description
            if original_description:
                self.df.at[idx, 'DESCRIPTION'] = original_description
        else:
            # Add new
            new_row = pd.DataFrame([{
                'GENIUS #': sku,
                'CUSTOM DESCRIPTION': custom_description,
                'DESCRIPTION': original_description
            }])
            self.df = pd.concat([self.df, new_row], ignore_index=True)
    
    def delete(self, sku: str):
        """Delete a SKU entry."""
        sku = str(sku).strip()
        self.df = self.df[self.df['GENIUS #'] != sku]
    
    def search(self, query: str) -> pd.DataFrame:
        """
        Search for SKUs or descriptions matching query.
        
        Args:
            query: Search term
            
        Returns:
            Filtered DataFrame with matches
        """
        if self.df is None or len(self.df) == 0:
            return pd.DataFrame()
        
        query = query.lower()
        mask = (
            self.df['GENIUS #'].str.lower().str.contains(query, na=False) |
            self.df['CUSTOM DESCRIPTION'].str.lower().str.contains(query, na=False) |
            self.df['DESCRIPTION'].str.lower().str.contains(query, na=False)
        )
        return self.df[mask]
    
    def get_missing_custom_descriptions(self) -> pd.DataFrame:
        """Return entries that don't have a custom description set."""
        if self.df is None:
            return pd.DataFrame()
        
        mask = self.df['CUSTOM DESCRIPTION'].isna() | (self.df['CUSTOM DESCRIPTION'].str.strip() == '')
        return self.df[mask]
