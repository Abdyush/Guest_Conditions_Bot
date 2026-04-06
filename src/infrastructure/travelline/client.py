from __future__ import annotations

import json
import logging
import socket
import time
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.infrastructure.travelline.contracts import JSONDict, TravellineHTTPResponse


class TravellineClientError(RuntimeError):
    pass


class TravellineClientTimeout(TravellineClientError):
    pass


logger = logging.getLogger(__name__)
RETRYABLE_HTTP_STATUSES = frozenset({502, 503, 504})


@dataclass(frozen=True, slots=True)
class TravellineClient:
    base_url: str = "https://ru-ibe.tlintegration.ru/ApiWebDistribution/BookingForm"
    timeout_seconds: float = 20.0
    user_agent: str = "guest_conditions_bot/1.0"
    opener: Callable[..., object] = urlopen
    retry_count: int = 2
    retry_pause_seconds: float = 1.0

    def build_url(self, path: str, *, params: dict[str, str | int]) -> str:
        query = urlencode(params)
        base = self.base_url.rstrip("/")
        url = f"{base}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"
        return url

    def get_json(self, path: str, *, params: dict[str, str | int]) -> JSONDict:
        return self.get_json_response(path, params=params)["payload"]

    def get_json_response(self, path: str, *, params: dict[str, str | int]) -> TravellineHTTPResponse:
        url = self.build_url(path, params=params)
        logger.info("travelline_request path=%s url=%s", path, url)
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        attempts_total = self.retry_count + 1
        for attempt in range(1, attempts_total + 1):
            try:
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    raw = response.read()
                    status = int(getattr(response, "status", 200))
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception as exc:  # pragma: no cover
                    raise TravellineClientError(f"invalid_json path={path}") from exc
                if not isinstance(payload, dict):
                    raise TravellineClientError(f"invalid_payload_type path={path} type={type(payload).__name__}")
                return TravellineHTTPResponse(status=status, payload=payload)
            except HTTPError as exc:
                if exc.code in RETRYABLE_HTTP_STATUSES and attempt < attempts_total:
                    logger.warning(
                        "travelline_retry path=%s attempt=%s/%s reason=http_%s",
                        path,
                        attempt,
                        attempts_total,
                        exc.code,
                    )
                    time.sleep(self.retry_pause_seconds * attempt)
                    continue
                raise TravellineClientError(f"http_error status={exc.code} path={path}") from exc
            except (socket.timeout, TimeoutError) as exc:
                if attempt >= attempts_total:
                    raise TravellineClientTimeout(f"timeout path={path}") from exc
                logger.warning(
                    "travelline_retry path=%s attempt=%s/%s reason=timeout",
                    path,
                    attempt,
                    attempts_total,
                )
                time.sleep(self.retry_pause_seconds * attempt)
            except URLError as exc:
                if isinstance(exc.reason, socket.timeout):
                    if attempt >= attempts_total:
                        raise TravellineClientTimeout(f"timeout path={path}") from exc
                    logger.warning(
                        "travelline_retry path=%s attempt=%s/%s reason=timeout",
                        path,
                        attempt,
                        attempts_total,
                    )
                    time.sleep(self.retry_pause_seconds * attempt)
                    continue
                if attempt >= attempts_total:
                    raise TravellineClientError(f"network_error path={path} detail={exc.reason}") from exc
                logger.warning(
                    "travelline_retry path=%s attempt=%s/%s reason=%s",
                    path,
                    attempt,
                    attempts_total,
                    exc.reason,
                )
                time.sleep(self.retry_pause_seconds * attempt)
