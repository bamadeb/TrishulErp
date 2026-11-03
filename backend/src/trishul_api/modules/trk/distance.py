"""Travelled distance of a trip from its GPS trail.

Phone fixes are noisy: network/weak-signal fixes (accuracy of 50-500 m) jump around the true
position, and every jump adds a spike to a naive sum of point-to-point distances. The trail is
therefore cleaned first, then summed from the last *accepted* fix.
"""

from dataclasses import dataclass
from datetime import datetime
from math import asin, cos, radians, sin, sqrt

# Fixes less accurate than this are ignored. Calibrated on a real trip (trip 9): the distance
# summed from raw points was 10.52 km against ~5.8 km actually driven; 30 m gave 5.73 km.
MAX_ACCURACY_M = 30.0
# A hop faster than this is a GPS glitch, not driving.
MAX_SPEED_KMPH = 120.0
# Movement below this is GPS drift while standing still. It is not added, and the reference
# point stays put, so slow real movement still accumulates once it exceeds the threshold.
MIN_MOVE_M = 5.0


@dataclass(frozen=True, slots=True)
class GpsFix:
    recorded_at: datetime
    latitude: float
    longitude: float
    accuracy_m: float | None = None
    is_mock_location: bool = False


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * asin(sqrt(h))


def raw_route_km(fixes: list[GpsFix]) -> float:
    return sum(
        haversine_km((fixes[i - 1].latitude, fixes[i - 1].longitude), (fixes[i].latitude, fixes[i].longitude))
        for i in range(1, len(fixes))
    )


def route_distance_km(fixes: list[GpsFix]) -> float | None:
    """Distance travelled in km, or None when there are fewer than two fixes. Fixes must be in
    recorded_at order. If the trail is too poor to filter (fewer than two usable fixes), the raw
    sum is returned rather than a misleading 0."""
    if len(fixes) < 2:
        return None
    usable = [f for f in fixes if _usable(f)]
    if len(usable) < 2:
        return round(raw_route_km(fixes), 2)
    total = 0.0
    anchor: GpsFix | None = None
    for fix in usable:
        if anchor is None:
            anchor = fix
            continue
        seconds = (fix.recorded_at - anchor.recorded_at).total_seconds()
        if seconds <= 0:  # out of order or same instant
            continue
        km = haversine_km((anchor.latitude, anchor.longitude), (fix.latitude, fix.longitude))
        if km * 1000 < MIN_MOVE_M or km / (seconds / 3600) > MAX_SPEED_KMPH:
            continue
        total += km
        anchor = fix
    return round(total, 2)


def _usable(fix: GpsFix) -> bool:
    return not fix.is_mock_location and (fix.accuracy_m is None or fix.accuracy_m <= MAX_ACCURACY_M)
