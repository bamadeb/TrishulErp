from datetime import datetime, timedelta

from trishul_api.modules.trk.distance import GpsFix, accepted_fixes, gps_gaps, raw_route_km, route_distance_km

T0 = datetime(2026, 11, 3, 10, 0, 0)
# ~1.11 km per 0.01 degree of latitude
STEP = 0.001  # ~111 m


def fix(seconds: int, lat: float, lon: float = 85.0, accuracy: float | None = 5.0, mock: bool = False) -> GpsFix:
    return GpsFix(T0 + timedelta(seconds=seconds), lat, lon, accuracy, mock)


def straight(n: int, every: int = 10) -> list[GpsFix]:
    return [fix(i * every, 20.0 + i * STEP) for i in range(n)]


def test_fewer_than_two_points_has_no_distance() -> None:
    assert route_distance_km([]) is None
    assert route_distance_km([fix(0, 20.0)]) is None


def test_clean_trail_matches_the_plain_sum() -> None:
    fixes = straight(11)  # 10 hops of ~111 m at ~40 km/h
    assert route_distance_km(fixes) == round(raw_route_km(fixes), 2)


def test_inaccurate_fix_is_ignored() -> None:
    fixes = straight(11)
    fixes[5] = fix(50, 20.0 + 5 * STEP + 0.01, accuracy=250.0)  # a 1 km sideways spike
    assert route_distance_km(fixes) == round(raw_route_km(straight(11)), 2)


def test_impossible_speed_is_ignored_even_with_good_accuracy() -> None:
    fixes = straight(11)
    fixes[5] = fix(50, 20.0 + 5 * STEP + 0.02, accuracy=5.0)  # 2 km in 10 s
    assert route_distance_km(fixes) < raw_route_km(fixes)
    assert route_distance_km(fixes) == round(raw_route_km(straight(11)), 2)


def test_standing_still_drift_adds_nothing() -> None:
    drift = [fix(i * 3, 20.0 + (i % 2) * 0.00002) for i in range(20)]  # ~2 m wobble
    assert route_distance_km(drift) == 0.0


def test_slow_walk_still_accumulates() -> None:
    walk = [fix(i * 10, 20.0 + i * 0.00002) for i in range(60)]  # ~2.2 m every 10 s
    assert route_distance_km(walk) > 0.1


def test_mock_points_are_ignored() -> None:
    fixes = straight(6)
    fixes[3] = fix(30, 21.0, mock=True)
    assert route_distance_km(fixes) == round(raw_route_km(straight(6)), 2)


def test_out_of_order_fix_is_skipped() -> None:
    fixes = straight(6)
    fixes.insert(3, fix(5, 20.5))  # earlier than the previous accepted fix
    assert route_distance_km(fixes) == round(raw_route_km(straight(6)), 2)


def test_poor_trail_falls_back_to_the_raw_sum() -> None:
    fixes = [fix(i * 10, 20.0 + i * STEP, accuracy=300.0) for i in range(5)]
    assert route_distance_km(fixes) == round(raw_route_km(fixes), 2)
    assert route_distance_km(fixes) > 0


def test_missing_accuracy_is_trusted() -> None:
    fixes = [fix(i * 10, 20.0 + i * STEP, accuracy=None) for i in range(5)]
    assert route_distance_km(fixes) == round(raw_route_km(fixes), 2)


def test_distance_is_the_sum_over_the_accepted_trail() -> None:
    fixes = straight(11)
    fixes[5] = fix(50, 20.0 + 5 * STEP + 0.01, accuracy=250.0)
    assert route_distance_km(fixes) == round(raw_route_km(accepted_fixes(fixes)), 2)


def test_phone_silent_for_21_minutes_is_one_gap() -> None:
    # Trip 297: points near the start, nothing for 21 minutes, then points at the destination ~8 km away.
    start = [fix(i * 3, 20.0 + i * 0.0001) for i in range(20)]
    end = [fix(60 + 21 * 60 + i * 3, 20.075 + i * 0.0001) for i in range(10)]
    gaps = gps_gaps(start + end)
    assert len(gaps) == 1
    assert gaps[0].started_at == start[-1].recorded_at
    assert gaps[0].ended_at == end[0].recorded_at
    assert 7.5 < gaps[0].straight_km < 8.5


def test_standing_still_for_a_while_is_not_a_gap() -> None:
    # Ten minutes parked (no accepted fix because nothing moved), then driving on: under 0.5 km.
    parked = [fix(i * 3, 20.0) for i in range(5)] + [fix(600 + i * 10, 20.0 + i * STEP) for i in range(4)]
    assert gps_gaps(parked) == []


def test_a_short_hole_while_driving_is_not_a_gap() -> None:
    # 90 seconds without a fix over ~1 km (a flyover or tunnel) stays under the 2-minute limit.
    fixes = [*straight(5), fix(40 + 90, 20.0 + 4 * STEP + 0.009)]
    assert gps_gaps(fixes) == []


def test_weak_fixes_inside_a_hole_do_not_hide_the_gap() -> None:
    start = straight(5)
    weak = [fix(100 + i * 30, 20.01 + i * 0.01, accuracy=200.0) for i in range(5)]
    end = [fix(400, 20.07), fix(403, 20.0701)]
    gaps = gps_gaps(start + weak + end)
    assert len(gaps) == 1 and gaps[0].straight_km > 6
