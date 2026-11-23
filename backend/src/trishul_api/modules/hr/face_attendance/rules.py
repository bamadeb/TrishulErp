"""Pure rules for face attendance: India date, distance to a geofence, the nearest work location."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

IST_OFFSET = timedelta(hours=5, minutes=30)
EARTH_RADIUS_M = 6_371_000.0


def india_date(utc: datetime) -> date:
    """The attendance date of a UTC time (DATETIME2 columns hold UTC; attendance days are Indian days)."""
    return (utc + IST_OFFSET).date()


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, a)))


@dataclass(frozen=True, slots=True)
class Geofence:
    id: int
    latitude: Decimal | float
    longitude: Decimal | float
    radius_m: int


@dataclass(frozen=True, slots=True)
class GeofenceHit:
    work_location_id: int
    distance_m: float
    inside: bool


def nearest_geofence(lat: float, lon: float, fences: Iterable[Geofence]) -> GeofenceHit | None:
    """The closest work location and whether the point is inside its radius; None when there are none."""
    best: GeofenceHit | None = None
    for fence in fences:
        d = distance_m(lat, lon, float(fence.latitude), float(fence.longitude))
        if best is None or d < best.distance_m:
            best = GeofenceHit(work_location_id=fence.id, distance_m=d, inside=d <= fence.radius_m)
    return best
