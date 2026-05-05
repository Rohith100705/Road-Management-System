from __future__ import annotations

import json
import urllib.request
import urllib.error
from functools import lru_cache

from config import Config

try:
    import googlemaps
except ImportError:  # pragma: no cover
    googlemaps = None


def google_maps_ready() -> bool:
    """Return True when the Google Maps client library and API key are available."""
    return googlemaps is not None and bool(Config.GOOGLE_MAPS_API_KEY)


@lru_cache(maxsize=256)
def get_address_osm(lat: float, lng: float) -> str:
    """Fallback to free OpenStreetMap Nominatim API."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}"
        req = urllib.request.Request(url, headers={'User-Agent': 'RoadWatchAI/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if "display_name" in data:
                return data["display_name"]
            return "Unknown Location"
    except Exception as exc:
        print(f"[MAPS][WARN] OSM Fallback geocoding failed: {exc}")
        return "Unknown Location"


@lru_cache(maxsize=256)
def get_address(lat: float, lng: float) -> str:
    """
    Reverse geocode coordinates to street address using Google Maps API.
    If the API Key restricts access or fails, gracefully fallback to OpenStreetMap.
    """
    try:
        if googlemaps is None or not Config.GOOGLE_MAPS_API_KEY:
            return get_address_osm(lat, lng)
            
        client = googlemaps.Client(key=Config.GOOGLE_MAPS_API_KEY)
        results = client.reverse_geocode((lat, lng))
        if not results:
            return get_address_osm(lat, lng)
        return results[0].get("formatted_address", "Unknown Location")
    except Exception as exc:
        print(f"[MAPS][WARN] Google Maps geocoding failed ({exc}). Using OSM fallback.")
        return get_address_osm(lat, lng)


def get_maps_link(lat: float, lng: float) -> str:
    """Return a clickable Google Maps URL for the coordinates."""
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


def detect_zone(address: str) -> str:
    """
    Try to detect zone name from address string.
    Return 'Unknown Zone' if not detectable.
    """
    try:
        if not address or address == "Unknown Location":
            return "Unknown Zone"
        parts = [part.strip() for part in address.split(",") if part.strip()]
        if len(parts) >= 3:
            return parts[-3]
        if parts:
            return parts[0]
        return "Unknown Zone"
    except Exception as exc:
        print(f"[MAPS][WARN] Zone detection failed: {exc}")
        return "Unknown Zone"
