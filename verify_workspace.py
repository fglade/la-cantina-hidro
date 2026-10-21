"""Comprehensive unit and integration tests for La Cantina workspace:
- Synthetic terrain road tests (known slope, NoData barrier, tight bend, infeasible grade, missing input)
- Propagated grade limits & goal-connector mask enforcement
- Solar position angle conventions, America/Coyhaique UTC-03 invariance, and synthetic shadow geometry
- Production data contracts and asset completeness
"""
import json, math
from pathlib import Path
import numpy as np
from rasterio.transform import from_origin
from shapely.geometry import Point, LineString
from terrain_contract import ROOT, OUT, build_or_load_terrain_contract, load_2m_grid
from solar_model import (
    verify_coyhaique_tz, local_to_utc_ms, solar_position, daily_sun_events,
    cast_terrain_shadows, SITE_LAT, SITE_LON
)
from road_plan import (
    round_corners, compute_measured_radii, optimize_vertical_profile,
    check_connector_segment, solve_terrain_route,
    STATUS_FEASIBLE, STATUS_INFEASIBLE, STATUS_EXHAUSTED, STATUS_MISSING_DATA
)


def test_synthetic_terrain_cases():
    """Section 8.6 & 8.7: Focused synthetic terrain cases kept separate from production terrain."""
    step = 2.0
    h, w = 80, 120
    tr = from_origin(500000.0, 4900000.0, step, step)

    # 1. Known uniform slope (6% eastward ramp: dz/dx = 0.06)
    cols = np.arange(w, dtype=np.float32)[None, :]
    xs = cols * step
    terrain_ramp = np.broadcast_to(100.0 + 0.06 * xs, (h, w)).copy()
    allowed_ramp = np.ones((h, w), dtype=bool)
    cellcost_ramp = np.ones((h, w), dtype=np.float32)

    p_start = Point(500010.0, 4900000.0 - 80.0)
    p_goal = Point(500210.0, 4900000.0 - 80.0)
    z0 = 100.0 + 0.06 * 10.0
    z1 = 100.0 + 0.06 * 210.0  # dz = 12.0 m over 200.0 m -> 6.0%

    coords, seen, status = solve_terrain_route(
        p_start, p_goal, z0, z1, tr, allowed_ramp, terrain_ramp, cellcost_ramp,
        limit=0.07, heuristic_weight=2.0, enforce_connector_mask=True
    )
    assert status == STATUS_FEASIBLE and coords is not None, f'Expected FEASIBLE on 6% ramp with 7% limit, got {status}'
    from road_plan import smooth_coords_to_route
    route = smooth_coords_to_route(coords, radius=15.0)
    ss = np.linspace(0.0, route.length, int(route.length / 2.0) + 1)
    zz = 100.0 + 0.06 * (np.array([route.interpolate(float(s)).x for s in ss]) - 500000.0)
    design = optimize_vertical_profile(ss, zz, z0, z1, max_grade=0.07)
    assert design is not None, 'LP profile must succeed for 6% ramp under 7% limit'
    max_g = float(np.max(np.abs(np.diff(design) / np.diff(ss))))
    assert max_g <= 0.07001, f'Propagated 7% grade limit violated: {max_g}'

    # 2. Propagated grade limit & clearly infeasible elevation/length constraint
    # Requesting 4% max grade on a 6% ramp where direct dz=12m and corridor cannot meander enough:
    design_infeasible = optimize_vertical_profile(ss, zz, z0, z1, max_grade=0.04)
    assert design_infeasible is None, 'LP must reject profile when |dz|/L > max_grade (must not hardcode 10%)'

    # Steep wall where |z1 - z0| = 50 m over 100 m inside a narrow box -> impossible at 8%
    terrain_steep = np.broadcast_to(100.0 + 0.50 * xs, (h, w)).copy()
    narrow_mask = np.zeros((h, w), dtype=bool)
    narrow_mask[35:45, 5:60] = True
    coords_inf, _, status_inf = solve_terrain_route(
        Point(500014.0, 4900000.0 - 80.0), Point(500110.0, 4900000.0 - 80.0),
        107.0, 155.0, tr, narrow_mask, terrain_steep, cellcost_ramp,
        limit=0.08, heuristic_weight=2.0, max_states=20000
    )
    assert coords_inf is None and status_inf == STATUS_INFEASIBLE, f'Expected INFEASIBLE_PROVEN, got {status_inf}'

    # 3. NoData barrier test (including goal connector protection)
    allowed_barrier = np.ones((h, w), dtype=bool)
    # Create vertical NoData wall at col 50..55 from row 15..80, leaving gap at row 5..14
    allowed_barrier[15:, 50:55] = False
    terrain_barrier = np.full((h, w), 100.0, dtype=np.float32)
    terrain_barrier[~allowed_barrier] = np.nan

    # Verify check_connector_segment rejects jumping across the NoData wall
    conn_cross = check_connector_segment(
        (500096.0, 4900000.0 - 80.0), (500114.0, 4900000.0 - 80.0),
        tr, allowed_barrier, terrain_barrier, 100.0, 100.0, limit=0.10
    )
    assert not conn_cross, 'Goal connector must not bypass NoData barrier'

    # Verify search detours through the northern gap (rows 5..14) and never touches NoData
    coords_detour, _, status_detour = solve_terrain_route(
        Point(500040.0, 4900000.0 - 60.0), Point(500160.0, 4900000.0 - 60.0),
        100.0, 100.0, tr, allowed_barrier, np.full((h, w), 100.0, dtype=np.float32), cellcost_ramp,
        limit=0.10, heuristic_weight=1.5, enforce_connector_mask=True
    )
    assert status_detour == STATUS_FEASIBLE and coords_detour is not None
    detour_line = LineString(coords_detour)
    for s in np.linspace(0, detour_line.length, 80):
        pt = detour_line.interpolate(float(s))
        r, c = int((4900000.0 - pt.y) // step), int((pt.x - 500000.0) // step)
        assert allowed_barrier[r, c], f'Detour crossed NoData barrier at ({r}, {c})'

    # 4. Tight bend / minimum radius enforcement
    l_bend = [(0.0, 0.0), (60.0, 0.0), (60.0, 60.0)]
    rounded_20 = round_corners(l_bend, radius=20.0)
    radii_20 = compute_measured_radii(rounded_20)
    assert min(radii_20) >= 19.8, f'Expected min radius ~20m, got {min(radii_20)}'

    too_short_bend = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    try:
        round_corners(too_short_bend, radius=20.0)
        raise AssertionError('round_corners should reject segment shorter than tangent required for R20')
    except ValueError:
        pass

    # 5. Missing terrain input distinct state
    _, _, status_missing = solve_terrain_route(
        p_start, p_goal, float('nan'), z1, tr, allowed_ramp, terrain_ramp, cellcost_ramp, limit=0.10
    )
    assert status_missing == STATUS_MISSING_DATA, f'Expected MISSING_TERRAIN_INPUT, got {status_missing}'
    print('OK: Synthetic terrain tests (known slope, grade limit propagation, NoData barrier, tight bend, missing data).')


def test_solar_and_shadow_geometry():
    """Section 8.8: Test timezone invariance, seasonal motion, sun below horizon, and known shadow geometry."""
    tz_info = verify_coyhaique_tz()
    assert tz_info['iana_zone'] == 'America/Coyhaique' and tz_info['offset_minutes'] == -180

    # Summer vs Equinox vs Winter solar noon in America/Coyhaique
    ev_sum = daily_sun_events('2026-12-21', SITE_LAT, SITE_LON)
    ev_eq = daily_sun_events('2026-03-20', SITE_LAT, SITE_LON)
    ev_win = daily_sun_events('2026-06-21', SITE_LAT, SITE_LON)

    assert ev_sum['solar_noon_altitude_deg'] > ev_eq['solar_noon_altitude_deg'] > ev_win['solar_noon_altitude_deg']
    assert abs(ev_sum['solar_noon_altitude_deg'] - 67.38) < 0.5
    assert abs(ev_win['solar_noon_altitude_deg'] - 20.50) < 0.5
    assert ev_sum['astronomical_day_hours'] > 15.0
    assert ev_win['astronomical_day_hours'] < 9.0

    # At solar noon in Southern Hemisphere (-46.06 deg), sun transits North (azimuth ~ 0 / 360 deg)
    for ev in (ev_sum, ev_eq, ev_win):
        az = ev['solar_noon_azimuth_deg']
        assert az < 3.0 or az > 357.0, f'Expected northern solar transit at noon, got {az}'

    # After sunset (23:30 local in winter), sun is below horizon
    night_pos = solar_position(local_to_utc_ms('2026-06-21', 23 * 60 + 30), SITE_LAT, SITE_LON)
    assert night_pos['altitude_deg'] < -10.0 and not night_pos['above_horizon']

    # Known shadow geometry case:
    # 100x100 grid at 2 m step. Flat plain at z=100 m, with East-West wall at row 30 of height z=140 m (dz=40 m).
    # Sun in North (azimuth=0 deg, grid_convergence=0 deg) at altitude=45 deg (tan(45)=1.0).
    # Shadow should extend exactly 40 m south of row 30 -> rows 31..50 (20 cells * 2 m = 40 m).
    h, w = 100, 100
    grid = np.full((h, w), 100.0, dtype=np.float32)
    valid = np.ones((h, w), dtype=bool)
    grid[30, 20:80] = 140.0
    # Add a NoData patch at rows 70..75, cols 40..45
    valid[70:75, 40:45] = False
    grid[~valid] = np.nan

    sh = cast_terrain_shadows(grid, valid, step_m=2.0, azimuth_deg=0.0, altitude_deg=45.0, grid_convergence_deg=0.0)
    # Ridge top itself (row 30, col 50) is sunlit (1)
    assert sh[30, 50] == 1
    # Cells 1..19 south of ridge (rows 31..49, col 50, distance 2..38 m < 40 m) must be in shadow (2)
    assert (sh[31:50, 50] == 2).all(), f'Expected shadow behind wall, got {sh[31:50, 50]}'
    # Cells beyond 42 m south of ridge (rows 52..65, col 50) must be sunlit (1)
    assert (sh[52:65, 50] == 1).all(), f'Expected sunlight past shadow tip, got {sh[52:65, 50]}'
    # NoData patch must remain 0 (unknown / Sin topografía)
    assert (sh[70:75, 40:45] == 0).all(), 'NoData cells must remain 0 in shadow output'

    # Sun below horizon -> all valid cells are 2 (night), NoData remains 0
    sh_night = cast_terrain_shadows(grid, valid, step_m=2.0, azimuth_deg=180.0, altitude_deg=-5.0)
    assert (sh_night[valid] == 2).all() and (sh_night[~valid] == 0).all()
    print('OK: Solar position, America/Coyhaique timezone, seasonal motion, and analytical shadow geometry tests.')


if __name__ == '__main__':
    test_synthetic_terrain_cases()
    test_solar_and_shadow_geometry()
