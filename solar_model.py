"""Solar position (SunCalc v1.9.0 conventions adapted to True North clockwise)
and analytical terrain shadow / sun-hours calculation for La Cantina (America/Coyhaique, UTC-03)."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json, math
import numpy as np
from terrain_contract import (
    ROOT, OUT, load_2m_grid, save_web_rgba_overlay, compute_grid_convergence_deg
)

# Pinned solar algorithm identity
SUNCALC_VERSION = '1.9.0-adapted-true-north-cw'
SITE_TIMEZONE = 'America/Coyhaique'
SITE_UTC_OFFSET_HOURS = -3  # Permanent UTC-03 in Aysén since 2025
COYHAIQUE_TZ = timedelta(hours=SITE_UTC_OFFSET_HOURS)

# Site reference coordinates (inferred roundabout / property center)
SITE_LAT = -46.0627727
SITE_LON = -72.5959570

RAD = math.pi / 180.0
DEG = 180.0 / math.pi
DAY_MS = 1000.0 * 60.0 * 60.0 * 24.0
J1970 = 2440588.0
J2000 = 2451545.0
E_OBLIQ = RAD * 23.4397


def verify_coyhaique_tz() -> dict:
    """Verify America/Coyhaique timezone behavior and return diagnostics."""
    info = dict(iana_zone=SITE_TIMEZONE, fixed_utc_offset='-03:00', offset_minutes=-180, runtime_zoneinfo_ok=False)
    try:
        tz = ZoneInfo(SITE_TIMEZONE)
        dt_winter = datetime(2026, 6, 21, 12, 0, tzinfo=tz)
        dt_summer = datetime(2026, 12, 21, 12, 0, tzinfo=tz)
        off_w = dt_winter.utcoffset().total_seconds() / 60.0
        off_s = dt_summer.utcoffset().total_seconds() / 60.0
        info['runtime_zoneinfo_ok'] = (off_w == -180.0 and off_s == -180.0)
    except Exception:
        info['runtime_zoneinfo_ok'] = False
    return info


def local_to_utc_ms(date_str: str, minutes_from_midnight: float) -> int:
    """Convert site-local date (YYYY-MM-DD) and minutes [0..1440) in America/Coyhaique (UTC-03) to UTC epoch ms."""
    y, m, d = map(int, date_str.split('-'))
    base_local = datetime(y, m, d, 0, 0, 0, tzinfo=timezone(COYHAIQUE_TZ))
    dt = base_local + timedelta(minutes=float(minutes_from_midnight))
    return int(round(dt.timestamp() * 1000.0))


def utc_ms_to_local_iso(utc_ms: int) -> str:
    """Format UTC epoch ms as ISO string in America/Coyhaique (-03:00)."""
    dt = datetime.fromtimestamp(utc_ms / 1000.0, tz=timezone(COYHAIQUE_TZ))
    return dt.isoformat()


def solar_position(utc_ms: float, lat_deg: float = SITE_LAT, lon_deg: float = SITE_LON) -> dict:
    """Compute solar position using SunCalc v1.9.0 astronomical formulas.
    Returns azimuth_deg in [0, 360) clockwise from True North (0=N, 90=E, 180=S, 270=W)
    and altitude_deg in [-90, 90] above astronomical horizon.
    """
    d = (utc_ms / DAY_MS - 0.5 + J1970) - J2000
    lw = RAD * (-lon_deg)
    phi = RAD * lat_deg

    # Solar mean anomaly
    M = RAD * (357.5291 + 0.98560028 * d)
    # Equation of center
    C = RAD * (1.9148 * math.sin(M) + 0.0200 * math.sin(2 * M) + 0.0003 * math.sin(3 * M))
    # Ecliptic longitude
    P = RAD * 102.9372
    L = M + C + P + math.pi

    dec = math.asin(math.sin(0.0) * math.cos(E_OBLIQ) + math.cos(0.0) * math.sin(E_OBLIQ) * math.sin(L))
    ra = math.atan2(math.sin(L) * math.cos(E_OBLIQ), math.cos(L))

    # Sidereal time
    H = (RAD * (280.16 + 360.9856235 * d) - lw) - ra

    # Altitude
    sin_alt = math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(H)
    alt_rad = math.asin(max(-1.0, min(1.0, sin_alt)))

    # SunCalc azimuth (from South clockwise: 0=S, +pi/2=W, -pi/2=E, +-pi=N)
    az_south_rad = math.atan2(math.sin(H), math.cos(H) * math.sin(phi) - math.tan(dec) * math.cos(phi))
    # Convert to clockwise from True North:
    azimuth_deg = (az_south_rad * DEG + 180.0) % 360.0
    altitude_deg = alt_rad * DEG

    return dict(
        azimuth_deg=float(azimuth_deg),
        altitude_deg=float(altitude_deg),
        declination_deg=float(dec * DEG),
        above_horizon=bool(altitude_deg > 0.0),
    )


def daily_sun_events(date_str: str, lat_deg: float = SITE_LAT, lon_deg: float = SITE_LON) -> dict:
    """Find astronomical sunrise, solar noon, and sunset in site-local minutes (America/Coyhaique, UTC-03)."""
    # Sample every 2 minutes across the local civil day (0..1440)
    mins = np.arange(0, 1441, 2, dtype=np.float64)
    alts = np.array([solar_position(local_to_utc_ms(date_str, m), lat_deg, lon_deg)['altitude_deg'] for m in mins])
    azs = np.array([solar_position(local_to_utc_ms(date_str, m), lat_deg, lon_deg)['azimuth_deg'] for m in mins])

    noon_idx = int(np.argmax(alts))
    # Refine solar noon around peak
    best_m = float(mins[noon_idx])
    for dm in np.linspace(-2.0, 2.0, 41):
        m_try = max(0.0, min(1440.0, mins[noon_idx] + dm))
        a_try = solar_position(local_to_utc_ms(date_str, m_try), lat_deg, lon_deg)['altitude_deg']
        if a_try > alts[noon_idx]:
            alts[noon_idx] = a_try
            best_m = float(m_try)
    noon_pos = solar_position(local_to_utc_ms(date_str, best_m), lat_deg, lon_deg)

    # Astronomical horizon crossing (h0 = -0.833 deg for standard refraction + solar disc radius, and 0.0 deg geometric)
    h0 = -0.833
    above = alts >= h0
    sunrise_min = None
    sunset_min = None
    for i in range(len(mins) - 1):
        if not above[i] and above[i + 1]:
            t = (h0 - alts[i]) / max(1e-6, alts[i + 1] - alts[i])
            sunrise_min = float(mins[i] + t * 2.0)
        elif above[i] and not above[i + 1]:
            t = (alts[i] - h0) / max(1e-6, alts[i] - alts[i + 1])
            sunset_min = float(mins[i] + t * 2.0)

    def fmt_hm(m):
        if m is None:
            return '—'
        hh = int(round(m)) // 60
        mm = int(round(m)) % 60
        return f'{hh:02d}:{mm:02d}'

    sr_pos = solar_position(local_to_utc_ms(date_str, sunrise_min), lat_deg, lon_deg) if sunrise_min is not None else None
    ss_pos = solar_position(local_to_utc_ms(date_str, sunset_min), lat_deg, lon_deg) if sunset_min is not None else None

    return dict(
        date=date_str,
        timezone=SITE_TIMEZONE,
        utc_offset='-03:00',
        sunrise_minutes=round(sunrise_min, 1) if sunrise_min is not None else None,
        sunrise_time=fmt_hm(sunrise_min),
        sunrise_azimuth_deg=round(sr_pos['azimuth_deg'], 1) if sr_pos else None,
        solar_noon_minutes=round(best_m, 1),
        solar_noon_time=fmt_hm(best_m),
        solar_noon_altitude_deg=round(noon_pos['altitude_deg'], 2),
        solar_noon_azimuth_deg=round(noon_pos['azimuth_deg'], 1),
        sunset_minutes=round(sunset_min, 1) if sunset_min is not None else None,
        sunset_time=fmt_hm(sunset_min),
        sunset_azimuth_deg=round(ss_pos['azimuth_deg'], 1) if ss_pos else None,
        astronomical_day_hours=round((sunset_min - sunrise_min) / 60.0, 2) if (sunrise_min and sunset_min) else 0.0,
    )


def cast_terrain_shadows(grid: np.ndarray, valid: np.ndarray, step_m: float,
                         azimuth_deg: float, altitude_deg: float,
                         grid_convergence_deg: float = 0.0,
                         ray_stride_cells: int = 1) -> np.ndarray:
    """Compute analytical terrain shadow state on unexaggerated metric DTM grid:
    Returns uint8 array of shape (H, W):
      0 = NoData (Sin topografía)
      1 = Direct sun (Iluminado)
      2 = Cast terrain shadow (Sombra proyectada por el terreno)
      3 = Uncertain horizon edge (Rayo sale del borde DTM a baja altura solar <15 deg dentro de 80 m)
    """
    h, w = grid.shape
    state = np.zeros((h, w), dtype=np.uint8)
    if altitude_deg <= 0.0:
        state[valid] = 2
        return state

    grid_az_rad = math.radians((azimuth_deg - grid_convergence_deg) % 360.0)
    dx = math.sin(grid_az_rad)
    dy = -math.cos(grid_az_rad)

    tan_alt = math.tan(math.radians(altitude_deg))
    z_span = float(np.nanmax(grid[valid]) - np.nanmin(grid[valid])) if valid.any() else 250.0
    max_dist_m = min(math.hypot(h, w) * step_m, max(40.0, (z_span + 10.0) / max(0.03, tan_alt)))
    n_steps = int(math.ceil(max_dist_m / step_m))

    state[valid] = 1
    shadowed = np.zeros((h, w), dtype=bool)
    uncertain = np.zeros((h, w), dtype=bool)
    check_uncertain = altitude_deg < 15.0

    # Fast 2D slice shifting across the grid
    for s in range(1, n_steps + 1, max(1, ray_stride_cells)):
        dr = int(round(dy * s))
        dc = int(round(dx * s))
        if dr == 0 and dc == 0:
            continue
        r0 = max(0, -dr)
        r1 = min(h, h - dr)
        c0 = max(0, -dc)
        c1 = min(w, w - dc)
        if r0 >= r1 or c0 >= c1:
            break

        src_slice = (slice(r0, r1), slice(c0, c1))
        dst_slice = (slice(r0 + dr, r1 + dr), slice(c0 + dc, c1 + dc))

        dz = (s * step_m) * tan_alt
        v_src = valid[src_slice]
        v_dst = valid[dst_slice]
        both = v_src & v_dst
        hit = both & (grid[dst_slice] > grid[src_slice] + dz + 0.05)
        shadowed[src_slice] |= hit

        if check_uncertain and (s * step_m) < 80.0:
            # Ray exited valid mask or bounds before being shadowed
            uncertain[src_slice] |= (v_src & (~v_dst) & (~shadowed[src_slice]))
            if r0 > 0:
                uncertain[:r0, :] |= valid[:r0, :] & (~shadowed[:r0, :])
            if r1 < h:
                uncertain[r1:, :] |= valid[r1:, :] & (~shadowed[r1:, :])
            if c0 > 0:
                uncertain[:, :c0] |= valid[:, :c0] & (~shadowed[:, :c0])
            if c1 < w:
                uncertain[:, c1:] |= valid[:, c1:] & (~shadowed[:, c1:])

    state[valid & uncertain] = 3
    state[valid & shadowed] = 2
    return state


def compute_daily_sun_hours(grid: np.ndarray, valid: np.ndarray, step_m: float,
                            date_str: str, grid_convergence_deg: float = 0.0,
                            dt_minutes: float = 30.0) -> tuple[np.ndarray, dict]:
    """Integrate modeled clear-sky topographic direct sun hours across a civil day in America/Coyhaique."""
    events = daily_sun_events(date_str)
    sr = events['sunrise_minutes']
    ss = events['sunset_minutes']
    hours_grid = np.full(grid.shape, np.nan, dtype=np.float32)
    hours_grid[valid] = 0.0
    if sr is None or ss is None or ss <= sr:
        return hours_grid, events

    sample_mins = np.arange(sr + dt_minutes * 0.5, ss, dt_minutes)
    weight_hr = dt_minutes / 60.0
    for m in sample_mins:
        pos = solar_position(local_to_utc_ms(date_str, float(m)))
        if pos['altitude_deg'] <= 0.0:
            continue
        sh = cast_terrain_shadows(
            grid, valid, step_m, pos['azimuth_deg'], pos['altitude_deg'],
            grid_convergence_deg, ray_stride_cells=2
        )
        lit = (sh == 1) | (sh == 3)
        hours_grid[lit] += weight_hr

    events['terrain_sun_hours_median'] = round(float(np.nanmedian(hours_grid[valid])), 2)
    events['terrain_sun_hours_min'] = round(float(np.nanmin(hours_grid[valid])), 2)
    events['terrain_sun_hours_max'] = round(float(np.nanmax(hours_grid[valid])), 2)
    return hours_grid, events


def colorize_sun_hours(hours_grid: np.ndarray, valid: np.ndarray, max_hours: float = 15.5) -> np.ndarray:
    """Create RGBA (4, H, W) visualization for daily direct sun hours."""
    stops = np.array([0.0, 0.25, 0.50, 0.75, 1.0]) * max_hours
    colors = np.array([
        [32, 54, 92],     # deep shadow blue
        [65, 130, 158],   # cool teal
        [152, 198, 122],  # mild green-gold
        [242, 202, 82],   # warm gold
        [235, 118, 45],   # intense sun amber
    ], dtype=np.float32)
    h_val = np.nan_to_num(hours_grid, nan=0.0)
    rgba = np.zeros((4, *hours_grid.shape), dtype=np.uint8)
    for c in range(3):
        rgba[c] = np.interp(h_val, stops, colors[:, c]).astype(np.uint8)
    rgba[3] = np.where(valid, 200, 0).astype(np.uint8)
    return rgba


def build_solar_presets(force_rebuild: bool = False) -> dict:
    """Precompute seasonal solar summaries and sun-hour web overlays."""
    out_json = OUT / 'solar_presets.json'
    if not force_rebuild and out_json.exists() and (OUT / 'solar_hours_summer_web.png').exists():
        return json.loads(out_json.read_text(encoding='utf8'))

    grid, valid, inside, tr, payload = load_2m_grid()
    conv_deg = compute_grid_convergence_deg(SITE_LON, SITE_LAT)

    seasons = [
        ('summer', 'Solsticio de verano (Sur)', '2026-12-21'),
        ('equinox', 'Equinoccio (Otoño / Primavera)', '2026-03-20'),
        ('winter', 'Solsticio de invierno (Sur)', '2026-06-21'),
    ]
    presets = {}
    for key, label, date_str in seasons:
        hrs_grid, ev = compute_daily_sun_hours(grid, valid, payload['step_m'], date_str, conv_deg, dt_minutes=30.0)
        ev['label'] = label
        rgba = colorize_sun_hours(hrs_grid, valid, max_hours=15.5)
        save_web_rgba_overlay(rgba, tr, 'EPSG:32718', OUT / f'solar_hours_{key}_web.png', maxsize=900)
        presets[key] = ev

    result = dict(
        algorithm=SUNCALC_VERSION,
        timezone=verify_coyhaique_tz(),
        site_wgs84=dict(lat=SITE_LAT, lon=SITE_LON),
        grid_convergence_deg=round(conv_deg, 4),
        presets=presets,
        notes=dict(
            surface='DTM de terreno desnudo (bare-earth) a 2 m sin exageración vertical.',
            limitations=(
                'No incluye sombra de árboles ni edificaciones (requiere DSM filtrado/alturas de copa) '
                'ni obstrucción por cordones montañosos regionales fuera de la huella del DTM. '
                'Las horas de sol directo representan potencial topográfico de cielo despejado, no meteorología observada.'
            ),
        ),
    )
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
    return result


if __name__ == '__main__':
    res = build_solar_presets(force_rebuild=True)
    print('Solar presets built:', json.dumps(res['presets'], ensure_ascii=False, indent=2))
