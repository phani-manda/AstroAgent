import pytest
from tools.chart import compute_birth_chart, get_daily_transits


def test_missing_date_returns_error():
    result = compute_birth_chart({"time": "08:30", "place": "New York"})
    assert "error" in result
    assert "Incomplete" in result["error"]


def test_missing_place_returns_error():
    result = compute_birth_chart({"date": "1992-07-15", "time": "08:30"})
    assert "error" in result
    assert "Incomplete" in result["error"]


def test_invalid_date_format():
    result = compute_birth_chart({
        "date": "not-a-date", "time": "08:30", "place": "New York",
        "lat": 40.7, "lng": -74.0,
    })
    assert "error" in result


def test_invalid_month():
    result = compute_birth_chart({
        "date": "2000-13-01", "time": "08:30", "place": "New York",
        "lat": 40.7, "lng": -74.0,
    })
    assert "error" in result


def test_no_lat_lng_returns_error():
    result = compute_birth_chart({"date": "1992-07-15", "time": "08:30", "place": "New York"})
    assert "error" in result


def test_valid_chart_computation():
    result = compute_birth_chart({
        "date": "1992-07-15",
        "time": "08:30",
        "place": "New York",
        "lat": 40.7128,
        "lng": -74.006,
        "tz": "America/New_York",
    })

    assert "error" not in result
    assert "planets" in result
    assert "houses" in result
    assert "ascendant" in result
    assert "Sun" in result["planets"]
    assert "Moon" in result["planets"]
    assert result["planets"]["Sun"] > 0
    assert result["planets"]["Sun"] < 360
    assert result["planets"]["Moon"] > 0
    assert result["planets"]["Moon"] < 360


def test_planet_positions_reasonable():
    result = compute_birth_chart({
        "date": "2000-01-01",
        "time": "12:00",
        "place": "London",
        "lat": 51.5074,
        "lng": -0.1278,
        "tz": "Europe/London",
    })

    assert "error" not in result
    for planet in ["Sun", "Moon", "Mercury", "Venus", "Mars"]:
        assert result["planets"][planet] >= 0
        assert result["planets"][planet] < 360


def test_transits_with_valid_chart():
    chart = {
        "planets": {
            "Sun": 120.0,
            "Moon": 60.0,
        }
    }

    result = get_daily_transits("2026-05-29", chart)
    assert isinstance(result, list)


def test_transits_no_chart():
    result = get_daily_transits("2026-05-29", {})
    assert isinstance(result, list)
    assert len(result) > 0
    assert "error" in result[0]


def test_chart_ascendant_calculation():
    result = compute_birth_chart({
        "date": "1990-06-15",
        "time": "06:00",
        "place": "New York",
        "lat": 40.7128,
        "lng": -74.006,
        "tz": "America/New_York",
    })
    assert "error" not in result
    assert result["ascendant"] >= 0
    assert result["ascendant"] < 360
    assert result["mc"] >= 0
    assert result["mc"] < 360


def test_unknown_time_still_computes():
    result = compute_birth_chart({
        "date": "1995-04-10",
        "time": "unknown",
        "place": "Paris",
        "lat": 48.8566,
        "lng": 2.3522,
        "tz": "Europe/Paris",
    })
    assert "error" not in result
    assert "Sun" in result["planets"]
