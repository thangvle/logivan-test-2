from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class AddressInput:
    messy_address: str
    truck_plate: Optional[str] = None
    invoice_date: Optional[date] = None
    expected_location_id: Optional[int] = None


@dataclass
class AddressResolution:
    resolved_location_id: Optional[int]
    lat: Optional[float]
    lng: Optional[float]
    province: Optional[str]
    district: Optional[str]
    ward: Optional[str]
    confidence: str
    source: str
    used_rag_context: bool = False
    validation_result: Optional[dict] = None
