from __future__ import annotations

from typing import Any, Dict, Optional

from utils.geotagger import get_address, get_maps_link, google_maps_ready


class GoogleMapsClient:
    """Compatibility wrapper around the new geotagger helpers."""

    def __init__(self, api_key: Optional[str]) -> None:
        self.api_key = api_key

    @property
    def enabled(self) -> bool:
        """Return whether maps support is configured."""
        return google_maps_ready()

    def reverse_geocode(self, latitude: Optional[float], longitude: Optional[float]) -> Optional[Dict[str, Any]]:
        """Return a small reverse geocode payload."""
        if latitude is None or longitude is None:
            return None
        address = get_address(latitude, longitude)
        return {
            "formatted_address": address,
            "place_id": None,
            "types": [],
            "google_maps_url": get_maps_link(latitude, longitude),
        }


def build_google_maps_url(latitude: Optional[float], longitude: Optional[float]) -> Optional[str]:
    """Build a browser-friendly Google Maps URL."""
    if latitude is None or longitude is None:
        return None
    return get_maps_link(latitude, longitude)
