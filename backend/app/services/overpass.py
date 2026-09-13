from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.fr/api/interpreter",
]
REQUEST_TIMEOUT = 20
CACHE_TTL = timedelta(minutes=5)


class OverpassError(RuntimeError):
    pass


class _TTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[datetime, Any]] = {}

    def get(self, key: str) -> Any | None:
        value = self._data.get(key)
        if value is None:
            return None
        expires_at, payload = value
        if datetime.now(timezone.utc) > expires_at:
            self._data.pop(key, None)
            return None
        return payload

    def set(self, key: str, payload: Any, ttl: timedelta = CACHE_TTL) -> None:
        self._data[key] = (datetime.now(timezone.utc) + ttl, payload)


_cache = _TTLCache()


def _build_query(south: float, west: float, north: float, east: float) -> str:
    # Query common POI/business tags that often carry a 'name'
    bbox = f"{south},{west},{north},{east}"
    query = f"""
[out:json][timeout:25];
(
  node["name"]["amenity"]({bbox});
  node["name"]["shop"]({bbox});
  node["name"]["office"]({bbox});
  node["name"]["tourism"]({bbox});
  way["name"]["amenity"]({bbox});
  way["name"]["shop"]({bbox});
  way["name"]["office"]({bbox});
  way["name"]["tourism"]({bbox});
  relation["name"]["amenity"]({bbox});
  relation["name"]["shop"]({bbox});
  relation["name"]["office"]({bbox});
  relation["name"]["tourism"]({bbox});
);
out center;
"""
    return query


def _element_to_company(el: dict[str, Any]) -> dict[str, Any] | None:
    tags = el.get("tags", {}) or {}
    name = tags.get("name") or tags.get("official_name")
    if not name:
        return None
    # center for ways/relations, lat/lon for nodes
    if el.get("type") in ("way", "relation"):
        center = el.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")
    else:
        lat = el.get("lat")
        lon = el.get("lon")

    category = tags.get("amenity") or tags.get("shop") or tags.get("office") or tags.get("tourism") or tags.get("craft")
    address_parts = []
    for part in ("addr:housename", "addr:housenumber", "addr:street", "addr:city", "addr:postcode", "addr:country"):
        v = tags.get(part)
        if v:
            address_parts.append(v)
    address = ", ".join(address_parts) if address_parts else None

    return {
        "id": f"overpass-{el.get('type')}-{el.get('id')}",
        "name": name,
        "latitude": float(lat) if lat is not None else None,
        "longitude": float(lon) if lon is not None else None,
        "category": category or "poi",
        "address": address,
        "raw_tags": tags,
    }


def query_companies(south: float, west: float, north: float, east: float) -> list[dict[str, Any]]:
    cache_key = f"overpass:{south}:{west}:{north}:{east}"
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    query = _build_query(south, west, north, east)
    last_exc: Exception | None = None
    payload = None
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Accept": "application/json, text/json, */*",
        "User-Agent": "MA-Deal-OS/1.0 (+https://github.com/)",
    }
    for url in OVERPASS_URLS:
        try:
            resp = requests.post(url, data=query.encode("utf-8"), timeout=REQUEST_TIMEOUT, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
            break
        except requests.HTTPError as http_exc:
            last_exc = http_exc
            try:
                resp = requests.get(url, params={"data": query}, timeout=REQUEST_TIMEOUT, headers=headers)
                resp.raise_for_status()
                payload = resp.json()
                break
            except Exception as exc:
                last_exc = exc
                continue
        except Exception as exc:
            last_exc = exc
            continue
    if payload is None:
        raise OverpassError(f"Overpass query failed: {last_exc}") from last_exc
    if not isinstance(payload, dict):
        raise OverpassError("Overpass returned invalid JSON")

    elements = payload.get("elements", [])
    companies: list[dict[str, Any]] = []
    for el in elements:
        try:
            mapped = _element_to_company(el)
            if mapped and mapped["latitude"] is not None and mapped["longitude"] is not None:
                companies.append(mapped)
        except Exception:
            continue

    # simple dedupe by (name, lat, lon)
    seen = set()
    deduped = []
    for c in companies:
        key = (c["name"].lower(), round(c["latitude"], 5), round(c["longitude"], 5))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    _cache.set(cache_key, deduped)
    return deduped
