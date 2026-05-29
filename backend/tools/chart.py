import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from tools.ephemeris import (
    datetime_to_jd,
    get_planet_position,
    PLANET_IDS,
    MAJOR_ASPECTS,
    ORB_BY_ASPECT,
    placidus_cusps,
)

logger = logging.getLogger(__name__)

PLANET_NAMES = {v: k for k, v in PLANET_IDS.items()}


def compute_birth_chart(birth: Dict[str, Any]) -> Dict[str, Any]:
    date_str = birth.get("date")
    time_str = birth.get("time")
    place_name = birth.get("place")
    lat = birth.get("lat")
    lng = birth.get("lng")
    tz = birth.get("tz")

    if not date_str or not place_name:
        return {"error": "Incomplete birth data"}

    try:
        date_parts = date_str.split("-")
        year = int(date_parts[0])
        month = int(date_parts[1])
        day = int(date_parts[2])
    except (ValueError, IndexError):
        return {"error": "Invalid date format"}

    if month < 1 or month > 12 or day < 1 or day > 31:
        return {"error": "Invalid date"}

    if lat is None or lng is None:
        return {"error": "Incomplete birth data - location needed"}

    utc_offset = 0.0
    if tz and tz != "UTC":
        try:
            from timezonefinder import TimezoneFinder
            import pytz
            tf = TimezoneFinder()
            tz_obj = pytz.timezone(tz)
            test_dt = datetime(year, month, day, 12, 0, 0)
            offset = tz_obj.utcoffset(test_dt)
            if offset:
                utc_offset = offset.total_seconds() / 3600.0
        except Exception:
            utc_offset = 0.0

    if time_str and time_str.lower() not in ("unknown", ""):
        try:
            time_parts = time_str.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
        except (ValueError, IndexError):
            return {"error": "Invalid time format"}
        utc_hour = hour - utc_offset + minute / 60.0
    else:
        utc_hour = 12.0 - utc_offset

    jd = datetime_to_jd(datetime(year, month, day, 0, 0, 0)) + utc_hour / 24.0
    logger.info(f"Julian Day: {jd:.4f} for {year}-{month:02d}-{day:02d} {utc_hour:.2f}h UTC")

    planets = {}
    for name in PLANET_IDS:
        try:
            lon = get_planet_position(name, jd)
            planets[name] = round(lon, 2)
        except Exception as e:
            logger.warning(f"Failed to calculate {name}: {e}")
            planets[name] = 0.0

    houses_dict = {}
    ascendant = 0.0
    mc_val = 0.0
    try:
        cusps, ascendant, mc_val = placidus_cusps(jd, lat, lng)
        for i in range(12):
            houses_dict[i + 1] = cusps[i]
    except Exception as e:
        logger.warning(f"House calculation failed: {e}")
        for i in range(12):
            houses_dict[i + 1] = 0.0

    result = {
        "planets": planets,
        "houses": houses_dict,
        "ascendant": ascendant,
        "mc": mc_val,
        "birth_date": date_str,
        "birth_time": time_str,
        "birth_place": place_name,
    }
    logger.info(f"Chart computed for {date_str} {time_str} {place_name}")
    return result


def get_daily_transits(date_str: str, chart: Dict[str, Any]) -> list:
    if not chart or "planets" not in chart:
        return [{"error": "Ephemeris unavailable"}]

    natal_planets = chart.get("planets", {})

    try:
        parts = date_str.split("-")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
    except (ValueError, IndexError):
        today = datetime.utcnow()
        year, month, day = today.year, today.month, today.day

    jd = datetime_to_jd(datetime(year, month, day, 12, 0, 0))

    transits = []
    for name in PLANET_IDS:
        try:
            t_lon = get_planet_position(name, jd)

            for n_name, n_lon in natal_planets.items():
                if name == n_name:
                    continue
                diff = abs(t_lon - n_lon)
                if diff > 180.0:
                    diff = 360.0 - diff

                for aspect_name, aspect_angle in MAJOR_ASPECTS.items():
                    orb = ORB_BY_ASPECT.get(aspect_name, 6.0)
                    deviation = abs(diff - aspect_angle)
                    if deviation <= orb:
                        transits.append({
                            "planet": name,
                            "aspect": aspect_name,
                            "natal_planet": n_name,
                            "orb": round(deviation, 2),
                        })
        except Exception as e:
            logger.warning(f"Transit calculation failed for {name}: {e}")
            continue

    transits.sort(key=lambda t: t["orb"])
    logger.info(f"Calculated {len(transits)} daily transits for {date_str}")
    return transits
