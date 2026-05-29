import pytest
from app.models import Conversation, Message, BirthInfo, ChartData, GeocodeResult


def test_message_model():
    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_birth_info_model():
    birth = BirthInfo(date="1992-07-15", time="08:30", place="New York")
    assert birth.date == "1992-07-15"
    assert birth.time == "08:30"


def test_chart_data_model():
    chart = ChartData(planets={"Sun": 120.5}, houses={1: 10.0}, ascendant=25.3, mc=180.0)
    assert chart.planets["Sun"] == 120.5


def test_geocode_result_model():
    geo = GeocodeResult(lat=40.7128, lng=-74.006, tz="America/New_York")
    assert geo.tz == "America/New_York"
