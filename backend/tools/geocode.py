import logging
import time
from typing import Optional, Dict, Any
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from timezonefinder import TimezoneFinder

logger = logging.getLogger(__name__)

_geolocator: Optional[Nominatim] = None
_tf: Optional[TimezoneFinder] = None

_GEOCODE_CACHE: Dict[str, Dict[str, Any]] = {}


def _get_geolocator() -> Nominatim:
    global _geolocator
    if _geolocator is None:
        _geolocator = Nominatim(user_agent="astroagent/1.0")
    return _geolocator


def _get_timezone_finder() -> TimezoneFinder:
    global _tf
    if _tf is None:
        _tf = TimezoneFinder()
    return _tf


def geocode_place(place_name: str) -> Dict[str, Any]:
    if not place_name or not place_name.strip():
        return {"error": "Place not found"}

    cache_key = place_name.strip().lower()
    if cache_key in _GEOCODE_CACHE:
        logger.info(f"Geocode cache hit for: {place_name}")
        return _GEOCODE_CACHE[cache_key]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            geolocator = _get_geolocator()
            location = geolocator.geocode(place_name, timeout=10)
            if location is None:
                logger.warning(f"Geocoding returned no results for: {place_name}")
                return {"error": "Place not found"}

            tf = _get_timezone_finder()
            timezone_str = tf.timezone_at(lat=location.latitude, lng=location.longitude)
            if timezone_str is None:
                timezone_str = "UTC"

            result = {
                "lat": round(location.latitude, 6),
                "lng": round(location.longitude, 6),
                "tz": timezone_str,
            }
            _GEOCODE_CACHE[cache_key] = result
            logger.info(f"Geocoded '{place_name}' -> {result}")
            return result

        except (GeocoderTimedOut, GeocoderUnavailable) as e:
            logger.warning(f"Geocoding attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))
            else:
                return {"error": "Geocoding service unavailable"}
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return {"error": "Geocoding failed"}

    return {"error": "Place not found"}
