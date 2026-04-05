from __future__ import annotations

from datetime import date
import io
import socket
from urllib.error import HTTPError
from urllib.error import URLError

import pytest

from src.infrastructure.travelline.availability_gateway import TravellineAvailabilityGateway
from src.infrastructure.travelline.client import TravellineClient, TravellineClientError, TravellineClientTimeout
from src.infrastructure.travelline.hotel_info_gateway import TravellineHotelInfoGateway


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self._payload


def test_travelline_client_happy_path() -> None:
    captured: dict[str, object] = {}

    def fake_open(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return _FakeResponse(b'{"ok": true, "room_types": []}')

    client = TravellineClient(base_url="https://example.test/base", timeout_seconds=7.5, opener=fake_open)
    payload = client.get_json("hotel_info", params={"hotelCode": "M1"})

    assert payload["ok"] is True
    assert captured["timeout"] == 7.5
    assert captured["url"] == "https://example.test/base/hotel_info?hotelCode=M1"


def test_travelline_client_response_includes_http_status() -> None:
    def fake_open(request, timeout):
        return _FakeResponseWithStatus(b'{"ok": true}', status=201)

    client = TravellineClient(opener=fake_open)
    response = client.get_json_response("hotel_info", params={"hotelCode": "M1"})

    assert response["status"] == 201
    assert response["payload"]["ok"] is True


def test_travelline_client_timeout_error() -> None:
    def fake_open(request, timeout):
        raise socket.timeout("boom")

    client = TravellineClient(opener=fake_open)
    with pytest.raises(TravellineClientTimeout):
        client.get_json("hotel_info", params={"hotelCode": "M1"})


def test_travelline_client_http_error() -> None:
    def fake_open(request, timeout):
        raise HTTPError(request.full_url, 500, "Internal Server Error", hdrs=None, fp=io.BytesIO(b"{}"))

    client = TravellineClient(opener=fake_open)
    with pytest.raises(TravellineClientError):
        client.get_json("hotel_info", params={"hotelCode": "M1"})


def test_travelline_client_retries_on_network_error() -> None:
    calls = {"count": 0}

    def fake_open(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise URLError("temporary")
        return _FakeResponse(b'{"ok": true}')

    client = TravellineClient(opener=fake_open, retry_count=1, retry_pause_seconds=0.0)
    payload = client.get_json("hotel_info", params={"hotelCode": "M1"})

    assert payload["ok"] is True
    assert calls["count"] == 2


def test_hotel_info_gateway_builds_real_query_contract() -> None:
    gateway = TravellineHotelInfoGateway(client=TravellineClient(opener=lambda *args, **kwargs: None), static_params={})

    params = gateway.build_params(hotel_code="5707")

    assert params == {
        "hotels[0].code": "5707",
        "language": "ru-ru",
    }


def test_availability_gateway_builds_real_query_contract() -> None:
    gateway = TravellineAvailabilityGateway(client=TravellineClient(opener=lambda *args, **kwargs: None), static_params={})

    params = gateway.build_params(
        hotel_code="5707",
        check_in=date(2026, 4, 5),
        check_out=date(2026, 4, 6),
        adults=6,
    )

    assert params == {
        "include_all_placements": "false",
        "include_promo_restricted": "true",
        "include_rates": "true",
        "include_transfers": "true",
        "language": "ru-ru",
        "criterions[0].adults": 6,
        "criterions[0].dates": "2026-04-05;2026-04-06",
        "criterions[0].hotels[0].code": "5707",
    }


class _FakeResponseWithStatus(_FakeResponse):
    def __init__(self, payload: bytes, *, status: int):
        super().__init__(payload)
        self.status = status
