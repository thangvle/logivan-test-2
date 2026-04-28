import re
import json
import unicodedata
from pathlib import Path
from typing import Optional


class Tier1Formatter:
    """
    Tier 1: Programmatic address formatting and normalization.
    
    Input: messy_address (str) with encoding issues
    Output: normalized_address (str) properly formatted
    
    Uses external JSON pattern file for scalability.
    """
    
    def __init__(self, pattern_file: str = "data/encoding_patterns.json"):
        self.pattern_file = Path(pattern_file)
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> dict:
        """Load encoding patterns from external JSON file."""
        if not self.pattern_file.exists():
            # Fallback to embedded patterns if file doesn't exist
            return self._get_default_patterns()
        
        with open(self.pattern_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            'phrases': data.get('patterns', []),
            'characters': data.get('character_mappings', [])
        }
    
    def _get_default_patterns(self) -> dict:
        """Fallback patterns if external file is missing."""
        return {
            'phrases': [
                {'from': 'Ph°Ýng', 'to': 'Phường'},
                {'from': '°Ýng', 'to': 'Đường'},
                {'from': 'Thành phÑ', 'to': 'Thành phố'},
                {'from': 'Thành phố HÓ', 'to': 'Thành phố Hồ'},
                {'from': 'Thành phố à L¡t', 'to': 'Thành phố Đà Lạt'},
                {'from': 'Lâm Óng', 'to': 'Lâm Đồng'},
                {'from': 'ViÇt Nam', 'to': 'Việt Nam'},
                {'from': 'HÓ Chí Minh', 'to': 'Hồ Chí Minh'},
            ],
            'characters': [
                {'from': '°', 'to': 'ư'},
                {'from': 'Ý', 'to': 'ý'},
                {'from': '§', 'to': 'ầ'},
                {'from': 'Ñ', 'to': 'ố'},
                {'from': 'Ó', 'to': 'đ'},
                {'from': '¡', 'to': 'à'},
            ]
        }
    
    def normalize_address(self, raw_address: str) -> str:
        """
        Normalize address to fix encoding issues and standardize format.
        
        Steps:
        1. Fix phrase-level patterns (long patterns first)
        2. Fix character-level mappings
        3. Normalize Unicode characters
        4. Standardize spacing and punctuation
        
        Args:
            raw_address: Raw address with potential encoding issues
            Example: "26 °Ýng Tr§n Khánh D°, Ph°Ýng 8, Thành phÑ à L¡t"
        
        Returns:
            Normalized address string
            Example: "26 Đường Trần Khánh Dư, Phường 8, Thành phố Đà Lạt"
        """
        if not raw_address:
            return ""
        
        result = raw_address
        
        # Step 1: Fix phrase-level patterns (priority 1-2)
        for pattern in self.patterns.get('phrases', []):
            result = result.replace(pattern['from'], pattern['to'])
        
        # Step 2: Fix character-level patterns (priority 3)
        for char_map in self.patterns.get('characters', []):
            result = result.replace(char_map['from'], char_map['to'])
        
        # Step 3: Normalize Unicode (NFC normalization)
        result = unicodedata.normalize('NFC', result)
        
        # Step 4: Clean whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        result = result.replace(' ,', ',').replace('  ', ' ')
        
        return result
    
    def add_pattern(self, from_text: str, to_text: str):
        """
        Add new pattern dynamically (for self-healing).
        Updates both in-memory patterns and external JSON file.
        """
        # Add to in-memory patterns
        new_pattern = {'from': from_text, 'to': to_text}
        self.patterns['phrases'].append(new_pattern)
        
        # Update external file
        if self.pattern_file.exists():
            with open(self.pattern_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['patterns'].append(new_pattern)
            with open(self.pattern_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    def extract_components(self, address: str) -> dict:
        """
        Extract address components (street, ward, district, province).
        
        Args:
            address: Normalized address string
        
        Returns:
            dict with extracted components
        """
        components = {
            'street': None,
            'ward': None,
            'district': None,
            'province': None,
            'full_address': address
        }
        
        # Split by comma
        parts = [p.strip() for p in address.split(',')]
        
        if len(parts) >= 1:
            components['street'] = parts[0]
        if len(parts) >= 2:
            # Check if it's a ward (Phường, Xã)
            if 'phường' in parts[1].lower() or 'xã' in parts[1].lower():
                components['ward'] = parts[1]
        if len(parts) >= 3:
            # Check if it's a district (Quận, Huyện)
            if 'quận' in parts[2].lower() or 'huyện' in parts[2].lower():
                components['district'] = parts[2]
            else:
                components['province'] = parts[2]
        if len(parts) >= 4:
            components['province'] = parts[3]
        
        return components
    
    def process(self, raw_address: str) -> dict:
        """
        Process address through Tier 1 formatter.
        
        Step-by-step logic:
        1. RECEIVE: Get raw address from VAT invoice
        2. NORMALIZE: Fix encoding issues, standardize format
        3. VALIDATE: Check if normalization was successful
        4. EXTRACT: Parse address components (street, ward, district, province)
        5. RETURN: Formatted address OR flag for Tier 2
        
        Args:
            raw_address: Address with encoding issues
            Example: "26 °Ýng Tr§n Khánh D°, Ph°Ýng 8, Thành phÑ à L¡t, Lâm Óng, ViÇt Nam"
        
        Returns:
            dict with status and formatted address
        """
        # Step 1: Normalize address
        normalized = self.normalize_address(raw_address)
        
        # Step 2: Check if normalization was successful
        accuracy = self._calculate_accuracy(raw_address, normalized)
        
        # Step 3: Extract components
        components = self.extract_components(normalized)
        
        # Step 4: Determine if Tier 1 can handle this
        if accuracy >= 0.8:
            return {
                "status": "TIER1_SUCCESS",
                "source": "TIER1_PROGRAMMATIC",
                "token_cost": 0,
                "accuracy": accuracy,
                "input": raw_address,
                "output": normalized,
                "components": components
            }
        else:
            # Tier 1 cannot handle - needs Tier 2
            return {
                "status": "TIER1_INCOMPLETE",
                "source": "TIER1_PROGRAMMATIC",
                "token_cost": 0,
                "accuracy": accuracy,
                "input": raw_address,
                "output": normalized,
                "components": components,
                "message": "Low accuracy normalization. Requires Tier 2/3."
            }
    
    def _calculate_accuracy(self, original: str, normalized: str) -> float:
        """
        Calculate accuracy score for normalization.
        
        Checks:
        1. Were corrupted characters found and fixed?
        2. Does the result still contain suspicious patterns?
        3. Are key Vietnamese address components present?
        
        Returns:
            float between 0.0 and 1.0
        """
        # Check 1: If no changes made, either perfect or unknown encoding
        if original == normalized:
            # Check if it contains known Vietnamese address keywords
            vietnamese_keywords = ['phường', 'quận', 'huyện', 'thành phố', 'tỉnh', 'xã']
            has_keywords = any(kw in normalized.lower() for kw in vietnamese_keywords)
            return 1.0 if has_keywords else 0.5
        
        # Check 2: Count suspicious characters remaining
        suspicious_chars = ['°', 'Ý', '§', 'Ñ', 'Ó', '¡', '­', 'Û', 'Ç', '¿', 'é']
        suspicious_count = sum(normalized.count(char) for char in suspicious_chars)
        
        if suspicious_count > 0:
            # Still has corrupted characters
            return 0.3
        
        # Check 3: Verify Vietnamese address structure
        vietnamese_keywords = ['phường', 'quận', 'huyện', 'thành phố', 'đường', 'việt nam']
        keyword_count = sum(1 for kw in vietnamese_keywords if kw in normalized.lower())
        
        # Confidence based on keyword presence
        if keyword_count >= 3:
            return 1.0
        elif keyword_count >= 2:
            return 0.9
        elif keyword_count >= 1:
            return 0.7
        else:
            return 0.5
