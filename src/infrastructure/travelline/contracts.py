from __future__ import annotations

from typing import TypedDict


JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]
JSONDict = dict[str, JSONValue]


class TravellineHTTPResponse(TypedDict):
    status: int
    payload: JSONDict
