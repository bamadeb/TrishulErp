"""Travelled distance of a trip from its GPS trail.

Phone fixes are noisy: network/weak-signal fixes (accuracy of 50-500 m) jump around the true
position, and every jump adds a spike to a naive sum of point-to-point distances. The trail is
therefore cleaned first, then summed from the last *accepted* fix.
"""

from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise
from math import asin, cos, radians, sin, sqrt

# Fixes less accurate than this are ignored. Calibrated on a real trip (trip 9): the distance
# summed from raw points was 10.52 km against ~5.8 km actually driven; 30 m gave 5.73 km.
MAX_ACCURACY_M = 30.0
# A hop faster than this is a GPS glitch, not driving.
MAX_SPEED_KMPH = 120.0
# Movement below this is GPS drift while standing still. It is not added, and the reference
# point stays put, so slow real movement still accumulates once it exceeds the threshold.
MIN_MOVE_M = 5.0
# Two accepted fixes this far apart in both time and space mean the phone recorded nothing in
# between (Android power saving or Doze stopping GPS, the app being closed): the real path is
# unknown and the distance counts the stretch as a straight line. A stop at a red light or a
# short tunnel stays under one of the two limits.
GAP_MIN_SECONDS = 120
GAP_MIN_KM = 0.5
# From this much untracked straight-line distance the trip's kilometres are likely short and
# need a person's check (the distance adjustment).
REVIEW_UNTRACKED_KM = 1.0


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


@dataclass(frozen=True, slots=True)
class GpsGap:
    """A stretch of the trip with no accepted fix: the phone recorded nothing usable in between."""

    started_at: datetime
    ended_at: datetime
    straight_km: float


def accepted_fixes(fixes: list[GpsFix]) -> list[GpsFix]:
    """The cleaned trail the distance is summed over: usable fixes (not fake, accuracy within
    MAX_ACCURACY_M), dropping standing-still drift and impossible jumps. Empty when fewer than two
    fixes are usable. Fixes must be in recorded_at order."""
    usable = [f for f in fixes if _usable(f)]
    if len(usable) < 2:
        return []
    kept = [usable[0]]
    for fix in usable[1:]:
        anchor = kept[-1]
        seconds = (fix.recorded_at - anchor.recorded_at).total_seconds()
        if seconds <= 0:  # out of order or same instant
            continue
        km = haversine_km((anchor.latitude, anchor.longitude), (fix.latitude, fix.longitude))
        if km * 1000 < MIN_MOVE_M or km / (seconds / 3600) > MAX_SPEED_KMPH:
            continue
        kept.append(fix)
    return kept


def route_distance_km(fixes: list[GpsFix]) -> float | None:
    """Distance travelled in km, or None when there are fewer than two fixes. Fixes must be in
    recorded_at order. If the trail is too poor to filter (fewer than two usable fixes), the raw
    sum is returned rather than a misleading 0."""
    if len(fixes) < 2:
        return None
    kept = accepted_fixes(fixes)
    if not kept:
        return round(raw_route_km(fixes), 2)
    return round(raw_route_km(kept), 2)


def gps_gaps(fixes: list[GpsFix]) -> list[GpsGap]:
    """Stretches of the cleaned trail where the phone recorded nothing for at least GAP_MIN_SECONDS
    while the position moved at least GAP_MIN_KM. The distance counts each as a straight line, so a
    trip with large gaps is usually longer than its GPS kilometres."""
    kept = accepted_fixes(fixes)
    gaps: list[GpsGap] = []
    for a, b in pairwise(kept):
        km = haversine_km((a.latitude, a.longitude), (b.latitude, b.longitude))
        if (b.recorded_at - a.recorded_at).total_seconds() >= GAP_MIN_SECONDS and km >= GAP_MIN_KM:
            gaps.append(GpsGap(started_at=a.recorded_at, ended_at=b.recorded_at, straight_km=round(km, 2)))
    return gaps


def _usable(fix: GpsFix) -> bool:
    return not fix.is_mock_location and (fix.accuracy_m is None or fix.accuracy_m <= MAX_ACCURACY_M)
