import json
from pathlib import Path
from typing import Optional
from src.models.address import AddressInput, AddressResolution


class Tier2Cache:
    """
    Tier 2: Semantic cache for similar addresses.
    Uses fuzzy matching to find previously resolved similar addresses.
    
    Input: messy_address (str)
    Output: AddressResolution | None
    """
    
    def __init__(self, cache_file: str = "data/tier2_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache = self._load_cache()
    
    def _load_cache(self) -> dict:
        """Load semantic cache from JSON file."""
        if not self.cache_file.exists():
            return {}
        
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _save_cache(self):
        """Save cache to JSON file."""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)
    
    def get(self, messy_address: str) -> Optional[AddressResolution]:
        """
        Check if similar address exists in Tier 2 cache.
        Uses exact match for now (can be enhanced with fuzzy matching).
        
        Args:
            messy_address: Raw address string
        
        Returns:
            AddressResolution if cache hit, None if miss
        """
        normalized_key = messy_address.lower().strip()
        
        if normalized_key in self.cache:
            cached = self.cache[normalized_key]
            return AddressResolution(
                resolved_location_id=cached.get('resolved_location_id'),
                lat=cached.get('lat'),
                lng=cached.get('lng'),
                province=cached.get('province'),
                district=cached.get('district'),
                ward=cached.get('ward'),
                confidence="HIGH",
                source="TIER2_CACHE",
                used_rag_context=False
            )
        
        return None
    
    def put(self, messy_address: str, resolution: AddressResolution):
        """
        Cache a resolution to Tier 2.
        
        Args:
            messy_address: Original raw address
            resolution: Validated AddressResolution
        """
        normalized_key = messy_address.lower().strip()
        
        self.cache[normalized_key] = {
            'resolved_location_id': resolution.resolved_location_id,
            'lat': resolution.lat,
            'lng': resolution.lng,
            'province': resolution.province,
            'district': resolution.district,
            'ward': resolution.ward,
            'source': resolution.source
        }
        
        self._save_cache()
