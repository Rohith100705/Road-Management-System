from __future__ import annotations

from datetime import datetime

from utils.geotagger import detect_zone, get_address, get_maps_link
from utils.storage import save_pothole


def create_and_save_report(
    lat: float,
    lng: float,
    image_path: str,
    severity: str = "Medium",
    confidence: float = 0.0,
) -> dict:
    """
    Build a complete pothole report:
    - Call geotagger.get_address() for street address
    - Call geotagger.detect_zone() for zone name
    - Call geotagger.get_maps_link() for clickable map link
    - Set status = 'Pending'
    - Set hazard_type = 'Pothole'
    - Set timestamp = datetime.now().isoformat()
    - Call storage.save_pothole() to save to MongoDB
    - Print 'Pothole saved: [address]'
    - Return the complete saved report dict
    """
    address = get_address(lat, lng)
    zone = detect_zone(address)
    report = {
        "hazard_type": "Pothole",
        "lat": lat,
        "lng": lng,
        "address": address,
        "zone": zone,
        "maps_link": get_maps_link(lat, lng),
        "image_path": image_path,
        "severity": severity.title(),
        "confidence": round(confidence, 4),
        "status": "Pending",
        "timestamp": datetime.now().isoformat(),
    }
    inserted_id = save_pothole(report)
    report["_id"] = inserted_id
    print(f"Pothole saved: {address}")
    return report
