"""Location Agent: place name or browser GPS -> district/state (+ lat/lon).

The advisory engine needs state and district to fetch weather, and
optionally latitude/longitude for SoilGrids. Farmers never type
coordinates.

    place text  -> state from text (lexicon) and/or OpenWeather direct geocoding
    browser GPS -> OpenWeather reverse geocoding

OpenWeather geocoding uses the same OPENWEATHER_API_KEY as the weather
service. Without a key, a place is accepted only when the farmer names
the state, and GPS coordinates are kept for soil lookup while the farmer
is asked for the place name.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from app.services import weather_service
from app.services.context_extraction_service import INDIAN_STATES, _extract_state
from app.services.text_utils import normalize_text


REVERSE_URL = "https://api.openweathermap.org/geo/1.0/reverse"


@dataclass
class ResolvedLocation:
    status: str  # resolved | needs_state | not_found | needs_place
    place: str | None = None
    district: str | None = None
    state: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    method: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def display(self) -> str:
        parts = [part for part in (self.district, self.state) if part]
        return ", ".join(parts) if parts else (self.place or "")


def _api_key() -> str | None:
    return weather_service.OPENWEATHER_API_KEY or None


def _strip_state(text: str, state_term: str | None) -> str:
    cleaned = text
    canonical = _canonical_state(state_term)
    if canonical:
        for alias in sorted(INDIAN_STATES[canonical] + [canonical], key=len, reverse=True):
            cleaned = re.sub(re.escape(alias), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(district|village|taluk|town|city)\b", " ", cleaned, flags=re.IGNORECASE)
    for word in ("जिला", "गांव", "गाँव", "மாவட்டம்", "கிராமம்", "జిల్లా", "గ్రామం"):
        cleaned = cleaned.replace(word, " ")
    return " ".join(cleaned.replace(",", " ").split()).strip()


def _canonical_state(term: str | None) -> str | None:
    if not term:
        return None
    norm = normalize_text(term)
    for state, aliases in INDIAN_STATES.items():
        if norm in {normalize_text(alias) for alias in aliases} or norm == normalize_text(state):
            return state
    return None


def _geocode(place: str, state: str | None) -> dict[str, Any] | None:
    key = _api_key()
    if not key:
        return None
    queries = [f"{place},{state},IN", f"{place},IN"] if state else [f"{place},IN"]
    with httpx.Client(timeout=10.0) as client:
        for query in queries:
            response = client.get(weather_service.GEOCODING_URL, params={"q": query, "limit": 5, "appid": key})
            response.raise_for_status()
            results = [item for item in response.json() if item.get("country") == "IN"]
            if state:
                same_state = [item for item in results if normalize_text(item.get("state")) == normalize_text(state)]
                results = same_state or results
            if results:
                return results[0]
    return None


def resolve_place(text: str) -> ResolvedLocation:
    raw = (text or "").strip()
    if not raw:
        return ResolvedLocation(status="needs_place")

    state, state_term = _extract_state(normalize_text(raw))
    place = _strip_state(raw, state_term) or raw

    try:
        hit = _geocode(place, state)
    except (httpx.HTTPError, ValueError):
        hit = None

    if hit:
        return ResolvedLocation(
            status="resolved",
            place=place,
            district=hit.get("name") or place,
            state=hit.get("state") or state,
            latitude=float(hit["lat"]),
            longitude=float(hit["lon"]),
            method="openweather_geocoding",
        )

    if state and place and normalize_text(place) != normalize_text(state):
        return ResolvedLocation(status="resolved", place=place, district=place, state=state, method="text")

    if _api_key():
        return ResolvedLocation(status="not_found", place=place, state=state)
    return ResolvedLocation(status="needs_state", place=place)


def resolve_coordinates(latitude: float, longitude: float) -> ResolvedLocation:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return ResolvedLocation(status="not_found")

    key = _api_key()
    if key:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    REVERSE_URL, params={"lat": latitude, "lon": longitude, "limit": 1, "appid": key}
                )
                response.raise_for_status()
                results = response.json()
            if results:
                hit = results[0]
                return ResolvedLocation(
                    status="resolved",
                    place=hit.get("name"),
                    district=hit.get("name"),
                    state=hit.get("state"),
                    latitude=latitude,
                    longitude=longitude,
                    method="openweather_reverse",
                )
        except (httpx.HTTPError, ValueError):
            pass

    return ResolvedLocation(status="needs_place", latitude=latitude, longitude=longitude, method="gps_only")
