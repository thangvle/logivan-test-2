import json
import os
from pathlib import Path
from typing import Optional
from src.models.address import AddressResolution
from src.models.validation import ValidationResult


class Validator:
    """
    Deterministic Validation Layer.
    
    Validates LLM/API results using objective Python checks (NO confidence scores).
    
    Validation Checks:
    1. Coordinate Distance Check (Google Maps API + Haversine formula)
    2. ID Integrity Check (location_id exists in database)
    3. Logprob Threshold Check (token probability > 0.8)
    
    Input: AddressResolution, GroundTruthData
    Output: ValidationResult (Pass/Fail + Routing Decision)
    """
    
    def __init__(self, ground_truth_file: str = "extracted-locations.json", 
                 google_maps_api_key: Optional[str] = None):
        self.ground_truth_file = Path(ground_truth_file)
        self.location_lookup = self._build_location_lookup()
        self.google_maps_api_key = google_maps_api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        
        # Import googlemaps only if API key is available
        self.gmaps = None
        if self.google_maps_api_key:
            try:
                import googlemaps
                self.gmaps = googlemaps.Client(key=self.google_maps_api_key)
            except ImportError:
                print("WARNING: googlemaps library not installed. Install with: pip install googlemaps")
    
    def _build_location_lookup(self) -> dict:
        """Build location ID lookup from ground truth data."""
        if not self.ground_truth_file.exists():
            return {}
        
        with open(self.ground_truth_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        lookup = {}
        for delivery in data.get('deliveries', []):
            for loc_type in ['pickup_location', 'dropoff_location']:
                location = delivery.get(loc_type, {})
                loc_id = location.get('id')
                if loc_id:
                    lookup[loc_id] = {
                        'lat': location.get('lat'),
                        'lng': location.get('lng'),
                        'description': location.get('description'),
                        'province': location.get('province'),
                        'district': location.get('district'),
                        'area': location.get('area')
                    }
        
        return lookup
    
    def validate(self, resolution: AddressResolution, 
                 expected_location_id: Optional[int] = None,
                 logprob: Optional[float] = None) -> ValidationResult:
        """
        Run all deterministic validation checks.
        
        Args:
            resolution: AddressResolution from LLM/API
            expected_location_id: Expected location ID (if known)
            logprob: Token probability from LLM (if available)
        
        Returns:
            ValidationResult with pass/fail and routing decision
        """
        checks = {}
        
        # Check 1: Coordinate Distance Check
        if expected_location_id and resolution.resolved_location_id:
            checks['coordinate_distance'] = self._coordinate_distance_check(
                resolution, expected_location_id
            )
        
        # Check 2: ID Integrity Check
        if resolution.resolved_location_id:
            checks['id_integrity'] = self._id_integrity_check(resolution)
        
        # Check 3: Logprob Threshold Check
        if logprob is not None:
            checks['logprob_threshold'] = self._logprob_check(logprob)
        
        # Determine overall pass/fail
        all_passed = all(check.get('passed', False) for check in checks.values())
        
        # Routing decision
        if all_passed:
            route_to = "TIER1_PROMOTION"
            reason = None
        else:
            route_to = "HUMAN_REVIEW_QUEUE"
            failed_checks = [name for name, check in checks.items() if not check.get('passed', False)]
            reason = f"Failed checks: {', '.join(failed_checks)}"
        
        return ValidationResult(
            passed=all_passed,
            checks=checks,
            route_to=route_to,
            human_review_reason=reason
        )
    
    def validate_coordinates(self, normalized_address: str) -> dict:
        """
        Validate address coordinates using Google Maps API.
        
        Args:
            normalized_address: Normalized address string
        
        Returns:
            dict with validation result
        """
        if not self.gmaps:
            return {
                'passed': False,
                'reason': 'Google Maps API not configured. Set GOOGLE_MAPS_API_KEY environment variable.',
                'google_maps_result': None
            }
        
        try:
            # Call Google Maps Geocoding API
            geocode_result = self.gmaps.geocode(normalized_address + ', Vietnam')
            
            if not geocode_result:
                return {
                    'passed': False,
                    'reason': 'Google Maps returned no results',
                    'google_maps_result': None
                }
            
            # Get coordinates from Google Maps
            location = geocode_result[0]['geometry']['location']
            formatted_address = geocode_result[0]['formatted_address']
            
            return {
                'passed': True,
                'google_maps_lat': location['lat'],
                'google_maps_lng': location['lng'],
                'formatted_address': formatted_address,
                'reason': None
            }
        
        except Exception as e:
            return {
                'passed': False,
                'reason': f'Google Maps API error: {str(e)}',
                'google_maps_result': None
            }
    
    def _coordinate_distance_check(self, resolution: AddressResolution, 
                                   expected_location_id: int) -> dict:
        """
        Check if resolved coordinates match Google Maps API result.
        
        Uses Google Maps Geocoding API to verify the address.
        """
        if not self.gmaps:
            return {
                'passed': False,
                'reason': 'Google Maps API not configured',
                'google_maps_result': None
            }
        
        # Build full address for Google Maps
        address_parts = []
        if resolution.ward:
            address_parts.append(resolution.ward)
        if resolution.district:
            address_parts.append(resolution.district)
        if resolution.province:
            address_parts.append(resolution.province)
        
        full_address = ', '.join(address_parts) + ', Vietnam'
        
        try:
            # Call Google Maps Geocoding API
            geocode_result = self.gmaps.geocode(full_address)
            
            if not geocode_result:
                return {
                    'passed': False,
                    'reason': 'Google Maps returned no results',
                    'google_maps_result': None
                }
            
            # Get coordinates from Google Maps
            location = geocode_result[0]['geometry']['location']
            google_lat = location['lat']
            google_lng = location['lng']
            
            # Compare with resolution coordinates
            if resolution.lat and resolution.lng:
                lat_diff = abs(google_lat - resolution.lat)
                lng_diff = abs(google_lng - resolution.lng)
                
                # Threshold: 0.05 degrees (~5km)
                threshold = 0.05
                passed = lat_diff <= threshold and lng_diff <= threshold
                
                return {
                    'passed': passed,
                    'google_maps_lat': google_lat,
                    'google_maps_lng': google_lng,
                    'resolution_lat': resolution.lat,
                    'resolution_lng': resolution.lng,
                    'lat_diff': round(lat_diff, 4),
                    'lng_diff': round(lng_diff, 4),
                    'threshold': threshold,
                    'reason': None if passed else f'Coordinate mismatch: lat_diff={lat_diff:.4f}, lng_diff={lng_diff:.4f}'
                }
            else:
                return {
                    'passed': False,
                    'reason': 'Resolution missing coordinates',
                    'google_maps_result': geocode_result[0]
                }
        
        except Exception as e:
            return {
                'passed': False,
                'reason': f'Google Maps API error: {str(e)}',
                'google_maps_result': None
            }
    
    def _id_integrity_check(self, resolution: AddressResolution) -> dict:
        """
        Check if resolved location_id exists in master database.
        """
        loc_id = resolution.resolved_location_id
        
        if loc_id in self.location_lookup:
            return {
                'passed': True,
                'location_id': loc_id,
                'reason': None
            }
        else:
            return {
                'passed': False,
                'location_id': loc_id,
                'reason': f'Location ID {loc_id} not found in master database'
            }
    
    def _logprob_check(self, logprob: float) -> dict:
        """
        Check if LLM token probability meets threshold.
        
        Threshold: 0.8 (80% probability)
        """
        threshold = 0.8
        passed = logprob >= threshold
        
        return {
            'passed': passed,
            'logprob': logprob,
            'threshold': threshold,
            'reason': None if passed else f'Logprob {logprob:.2f} below threshold {threshold}'
        }
