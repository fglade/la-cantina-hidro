"""Acceso nuevo desde desembocadura sur y motor de comparación de trazados viales; ignora CAMINOS del KML."""
from pathlib import Path
import json, math, heapq, csv
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.warp import reproject
from rasterio.transform import from_origin
from rasterio.features import rasterize
from rasterio.enums import Resampling
from scipy.ndimage import gaussian_filter, distance_transform_edt
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
from shapely.geometry import Point, LineString, Polygon
from inspect_data import read_kml

ROOT = Path(__file__).parent
OUT = ROOT / 'outputs'
STEP = 2.0
RADIUS = 15.0

STATUS_FEASIBLE = 'FEASIBLE'
STATUS_INFEASIBLE = 'INFEASIBLE_PROVEN'
STATUS_EXHAUSTED = 'SEARCH_EXHAUSTED'
STATUS_MISSING_DATA = 'MISSING_TERRAIN_INPUT'


def round_corners(coords, radius=RADIUS):
    out = [np.array(coords[0], dtype=float)]
    for a, v, b in zip(coords[:-2], coords[1:-1], coords[2:]):
        a, v, b = map(lambda x: np.array(x, dtype=float), (a, v, b))
        la = np.linalg.norm(v - a)
        lb = np.linalg.norm(b - v)
        if la < 1e-6 or lb < 1e-6:
            continue
        u = (v - a) / la
        w = (b - v) / lb
        theta = math.acos(float(np.clip(np.dot(u, w), -1.0, 1.0)))
        cross = u[0] * w[1] - u[1] * w[0]
        if theta < 1e-5:
            out.append(v)
            continue
        tangent = radius * math.tan(theta / 2.0)
        if tangent > 0.45 * min(la, lb):
            raise ValueError('Segmento insuficiente para radio de curva')
        p = v - u * tangent
        q = v + w * tangent
        sign = 1.0 if cross > 0 else -1.0
        center = p + sign * radius * np.array([-u[1], u[0]])
        alpha = math.atan2(*(p - center)[::-1])
        angles = alpha + sign * np.linspace(0.0, theta, max(5, int(theta * radius) + 1))
        out.extend(center + radius * np.array([math.cos(t), math.sin(t)]) for t in angles)
    out.append(np.array(coords[-1], dtype=float))
    return LineString(out)


def compute_measured_radii(line: LineString) -> list[float]:
    coords = list(line.coords)
    radii = []
    for a, b, c in zip(coords[:-2], coords[1:-1], coords[2:]):
        a, b, c = map(np.array, (a, b, c))
        ab = b - a
        bc = c - b
        lab = np.linalg.norm(ab)
        lbc = np.linalg.norm(bc)
        lca = np.linalg.norm(c - a)
        cross = abs(ab[0] * bc[1] - ab[1] * bc[0])
        if cross > 1e-5 and lab > 1e-4 and lbc > 1e-4:
            # Ignore collinear segments where angle change < 0.5 deg
            sin_theta = cross / (lab * lbc)
            if sin_theta > 0.0087:
                radii.append(float(lab * lbc * lca / (2.0 * cross)))
    return radii


def optimize_vertical_profile(ss: np.ndarray, zz: np.ndarray, z0: float, z1: float,
                              max_grade: float = 0.10, max_earthwork: float = 6.0,
                              max_grade_change: float | None = None):
    """Optimize vertical design profile using linear programming with propagated max_grade."""
    n = len(ss)
    if n < 2 or not np.isfinite(zz).all():
        return None
    ds = np.diff(ss)
    if (ds <= 0).any():
        return None
    # Check pure geometric feasibility between fixed endpoints
    if abs(z1 - z0) > max_grade * (ss[-1] - ss[0]) + 1e-6:
        return None

    extra_kink_rows = (2 * (n - 2)) if (max_grade_change is not None and n > 2) else 0
    total_rows = (4 * n - 2) + extra_kink_rows
    A = lil_matrix((total_rows, 2 * n))
    rhs = np.zeros(total_rows)

    for i in range(n):
        A[2 * i, i] = 1.0
        A[2 * i, n + i] = -1.0
        rhs[2 * i] = zz[i]
        A[2 * i + 1, i] = -1.0
        A[2 * i + 1, n + i] = -1.0
        rhs[2 * i + 1] = -zz[i]

    for i in range(n - 1):
        row = 2 * n + 2 * i
        limit_dz = float(max_grade) * float(ss[i + 1] - ss[i])
        A[row, i + 1] = 1.0
        A[row, i] = -1.0
        rhs[row] = limit_dz
        A[row + 1, i] = 1.0
        A[row + 1, i + 1] = -1.0
        rhs[row + 1] = limit_dz

    if max_grade_change is not None and n > 2:
        base_row = 4 * n - 2
        for i in range(1, n - 1):
            d0 = float(ss[i] - ss[i - 1])
            d1 = float(ss[i + 1] - ss[i])
            r_up = base_row + 2 * (i - 1)
            # (z_{i+1}-z_i)/d1 - (z_i-z_{i-1})/d0 <= max_grade_change
            A[r_up, i + 1] = 1.0 / d1
            A[r_up, i] = -1.0 / d1 - 1.0 / d0
            A[r_up, i - 1] = 1.0 / d0
            rhs[r_up] = float(max_grade_change)

            r_dn = r_up + 1
            A[r_dn, i + 1] = -1.0 / d1
            A[r_dn, i] = 1.0 / d1 + 1.0 / d0
            A[r_dn, i - 1] = -1.0 / d0
            rhs[r_dn] = float(max_grade_change)

    bounds = [(float(z) - max_earthwork, float(z) + max_earthwork) for z in zz] + [(0.0, None)] * n
    bounds[0] = (float(z0), float(z0))
    bounds[n - 1] = (float(z1), float(z1))
    lp = linprog(np.r_[np.zeros(n), np.ones(n)], A_ub=A.tocsr(), b_ub=rhs, bounds=bounds, method='highs')
    if not lp.success:
        return None
    return lp.x[:n]


def compute_grade_statistics(ss: np.ndarray, design: np.ndarray, zz: np.ndarray, max_grade_limit: float = 0.10) -> dict:
    """Compute detailed grade-band lengths, sustained steepness, and vertical kink metrics."""
    ds = np.diff(ss)
    dz = np.diff(design)
    signed_grades = dz / ds
    abs_grades_pct = np.abs(signed_grades) * 100.0
    total_len = float(ss[-1] - ss[0]) if len(ss) > 1 else 0.0

    b_lt_6 = float(ds[abs_grades_pct < 6.0].sum())
    b_6_8 = float(ds[(abs_grades_pct >= 6.0) & (abs_grades_pct < 8.0)].sum())
    b_8_10 = float(ds[(abs_grades_pct >= 8.0) & (abs_grades_pct <= 10.001)].sum())
    b_gt_10 = float(ds[abs_grades_pct > 10.001].sum())
    len_at_999 = float(ds[abs_grades_pct >= 9.99].sum())
    len_at_limit = float(ds[abs_grades_pct >= (max_grade_limit * 100.0 - 0.05)].sum())

    # Longest continuous steep climb >= 8.0% and >= 9.5%
    def max_continuous(threshold_pct: float) -> float:
        best = 0.0
        cur = 0.0
        for seg_l, g in zip(ds, abs_grades_pct):
            if g >= threshold_pct:
                cur += float(seg_l)
                if cur > best:
                    best = cur
            else:
                cur = 0.0
        return best

    grade_changes_pct = np.abs(np.diff(signed_grades)) * 100.0 if len(signed_grades) > 1 else np.array([0.0])
    ascent_m = float(np.maximum(dz, 0.0).sum())
    descent_m = float(np.maximum(-dz, 0.0).sum())

    return dict(
        ascent_m=round(ascent_m, 2),
        descent_m=round(descent_m, 2),
        max_design_grade_pct=round(float(np.max(abs_grades_pct)), 2) if len(abs_grades_pct) else 0.0,
        p95_design_grade_pct=round(float(np.percentile(abs_grades_pct, 95)), 2) if len(abs_grades_pct) else 0.0,
        mean_design_grade_pct=round(float(np.average(abs_grades_pct, weights=ds)), 2) if total_len > 0 else 0.0,
        length_at_or_above_9_99_pct_m=round(len_at_999, 2),
        pct_at_or_above_9_99_pct=round(100.0 * len_at_999 / max(1e-6, total_len), 1),
        length_near_grade_limit_m=round(len_at_limit, 2),
        pct_near_grade_limit=round(100.0 * len_at_limit / max(1e-6, total_len), 1),
        max_continuous_steep_8pct_m=round(max_continuous(8.0), 1),
        max_continuous_steep_9_5pct_m=round(max_continuous(9.5), 1),
        grade_bands_m=dict(
            under_6_pct=round(b_lt_6, 2),
            from_6_to_8_pct=round(b_6_8, 2),
            from_8_to_10_pct=round(b_8_10, 2),
            over_10_pct=round(b_gt_10, 2),
        ),
        max_vertical_grade_change_pct=round(float(np.max(grade_changes_pct)), 2),
        abrupt_vertical_changes_over_4pct_count=int((grade_changes_pct > 4.0).sum()),
    )


def evaluate_watercourses(route: LineString, streams_gdf: gpd.GeoDataFrame, endpoint_tol_m: float = 2.5) -> dict:
    """Evaluate all watercourses, distinguishing genuine crossings from endpoint contacts."""
    start_pt = Point(route.coords[0])
    end_pt = Point(route.coords[-1])
    contacts = []
    genuine = []
    legacy_list = []

    for _, s in streams_gdf.iterrows():
        inter = route.intersection(s.geometry)
        if inter.is_empty:
            continue
        legacy_list.append(dict(stream_id=int(s.id), tipo=str(s.tipo)))
        pts = []
        if inter.geom_type == 'Point':
            pts = [inter]
        elif inter.geom_type == 'MultiPoint':
            pts = list(inter.geoms)
        else:
            pts = [inter.centroid]

        for pt in pts:
            chainage_m = float(route.project(pt))
            near_start = pt.distance(start_pt) <= endpoint_tol_m or chainage_m <= endpoint_tol_m
            near_end = pt.distance(end_pt) <= endpoint_tol_m or (route.length - chainage_m) <= endpoint_tol_m
            entry = dict(
                stream_id=int(s.id),
                tipo=str(s.tipo),
                regimen='Permanente' if str(s.tipo) == 'arroyo' else 'No permanente (quebrada)',
                chainage_m=round(chainage_m, 1),
                classification='endpoint_contact' if (near_start or near_end) else 'genuine_crossing',
                work_required=(
                    'Conexión en cabecera/origen; requiere protección de ribera y drenaje de entrada, sin puente de cruce.'
                    if (near_start or near_end) else
                    ('Obra mayor / puente o marco en arroyo permanente' if str(s.tipo) == 'arroyo'
                     else 'Alcantarilla / badén drenante en quebrada estacional')
                ),
            )
            if near_start or near_end:
                contacts.append(entry)
            else:
                genuine.append(entry)

    return dict(
        all_intersections=legacy_list,
        endpoint_contacts=contacts,
        genuine_crossings=genuine,
        genuine_crossing_count=len(genuine),
        permanent_stream_crossings_count=sum(1 for x in genuine if x['tipo'] == 'arroyo'),
        seasonal_quebrada_crossings_count=sum(1 for x in genuine if x['tipo'] != 'arroyo'),
    )


def validate_platform_and_alignment(
    route: LineString, ss: np.ndarray, zz: np.ndarray, design: np.ndarray,
    sample_fn, boundary_geom, lots_gdf, streams_gdf,
    max_grade: float = 0.10, min_radius_m: float = 15.0,
    platform_m: float = 5.0, carriageway_m: float = 3.5,
    exclusion_polys: list | None = None,
) -> dict:
    """Comprehensive post-rounding, post-connector, and platform footprint validation."""
    radii = compute_measured_radii(route)
    min_r = float(min(radii)) if radii else 999.0
    is_simple = bool(route.is_simple)
    nodata_count = int((~np.isfinite(zz)).sum())
    nodata_len = float(nodata_count * (route.length / max(1, len(ss) - 1)))

    platform_poly = route.buffer(platform_m / 2.0)
    outside_axis_m = float(route.difference(boundary_geom).length) if boundary_geom is not None else 0.0
    outside_platform_m2 = float(platform_poly.difference(boundary_geom).area) if boundary_geom is not None else 0.0

    excl_overlap_m2 = 0.0
    if exclusion_polys:
        for ep in exclusion_polys:
            excl_overlap_m2 += float(platform_poly.intersection(ep).area)

    # Sample left and right edges of the modeled platform (+/- platform_m/2) to validate platform NoData and transverse cross-slope
    coords = np.array([route.interpolate(float(s)).coords[0] for s in ss])
    tangents = np.gradient(coords, axis=0)
    norms = np.linalg.norm(tangents, axis=1, keepdims=True)
    norms[norms < 1e-6] = 1.0
    tangents = tangents / norms
    normals = np.column_stack([-tangents[:, 1], tangents[:, 0]])
    half_w = platform_m / 2.0
    left_pts = [Point(xy) for xy in (coords + normals * half_w)]
    right_pts = [Point(xy) for xy in (coords - normals * half_w)]
    z_left = sample_fn(left_pts)
    z_right = sample_fn(right_pts)
    platform_edge_valid = np.isfinite(z_left) & np.isfinite(z_right)
    platform_valid_pct = float(100.0 * platform_edge_valid.sum() / max(1, len(ss)))
    cross_slopes_pct = np.abs(z_left[platform_edge_valid] - z_right[platform_edge_valid]) / max(0.5, platform_m) * 100.0
    cross_slope_p90 = float(np.percentile(cross_slopes_pct, 90)) if len(cross_slopes_pct) else 0.0

    # Estimate total formation width including 1:1 cut / 1.5:1 fill batters + 1.0 m ditch
    earth = np.abs(design - zz) if (design is not None and np.isfinite(zz).all()) else np.zeros_like(ss)
    batter_extra_w = earth * 1.25 * 2.0 + 1.0
    est_formation_max_w = float(platform_m + np.nanmax(batter_extra_w)) if len(batter_extra_w) else platform_m

    grades = np.abs(np.diff(design) / np.diff(ss)) if design is not None else np.zeros(max(1, len(ss) - 1))
    max_g = float(np.max(grades)) if len(grades) else 0.0

    wc = evaluate_watercourses(route, streams_gdf) if streams_gdf is not None else {}

    grade_ok = max_g <= (max_grade + 1e-4)
    radius_ok = min_r >= (min_radius_m - 0.25)
    nodata_ok = (nodata_count == 0) and (platform_valid_pct >= 98.0)
    boundary_ok = outside_axis_m < 0.05
    exclusion_ok = excl_overlap_m2 < 0.05

    return dict(
        all_constraints_satisfied=bool(is_simple and grade_ok and radius_ok and nodata_ok and boundary_ok and exclusion_ok),
        is_simple=is_simple,
        min_radius_target_m=round(min_radius_m, 2),
        min_radius_measured_m=round(min_r, 2),
        radius_ok=radius_ok,
        max_grade_target_pct=round(max_grade * 100.0, 2),
        max_grade_measured_pct=round(max_g * 100.0, 2),
        grade_ok=grade_ok,
        centerline_nodata_points=nodata_count,
        centerline_nodata_length_m=round(nodata_len, 2),
        platform_valid_coverage_pct=round(platform_valid_pct, 2),
        nodata_ok=nodata_ok,
        outside_property_axis_m=round(outside_axis_m, 2),
        outside_property_platform_m2=round(outside_platform_m2, 2),
        boundary_ok=boundary_ok,
        exclusion_overlap_m2=round(excl_overlap_m2, 2),
        exclusion_ok=exclusion_ok,
        cross_slope_p90_pct=round(cross_slope_p90, 1),
        modeled_platform_width_m=platform_m,
        modeled_carriageway_width_m=carriageway_m,
        estimated_max_formation_width_with_batters_m=round(est_formation_max_w, 1),
        unmodeled_footprint_note=(
            f'Huella validada para plataforma de {platform_m:.1f} m. '
            f'Con taludes preliminares de corte/relleno y cuneta lateral, la faja total de explanación puede alcanzar ~{est_formation_max_w:.1f} m '
            f'(pendiente transversal P90: {cross_slope_p90:.1f}%).'
        ),
        watercourse_evaluation=wc,
    )


def check_connector_segment(p0_xy, p1_xy, tr, allowed: np.ndarray, terrain: np.ndarray,
                            z_start_design: float, z_end_target: float, limit: float,
                            max_earthwork: float = 5.5) -> bool:
    """Validate an origin or goal connector against allowed mask, terrain NoData, grade limit, and earthwork."""
    h, w = allowed.shape
    dist = math.hypot(p1_xy[0] - p0_xy[0], p1_xy[1] - p0_xy[1])
    if dist < 1e-3:
        return True
    if abs(z_end_target - z_start_design) / dist > limit + 1e-4:
        return False
    n_samples = max(5, int(math.ceil(dist / (STEP * 0.5))) + 1)
    ts = np.linspace(0.0, 1.0, n_samples)
    xs = p0_xy[0] + ts * (p1_xy[0] - p0_xy[0])
    ys = p0_xy[1] + ts * (p1_xy[1] - p0_xy[1])
    rows, cols = rasterio.transform.rowcol(tr, xs, ys)
    rows = np.asarray(rows, dtype=int)
    cols = np.asarray(cols, dtype=int)
    if ((rows < 0) | (rows >= h) | (cols < 0) | (cols >= w)).any():
        return False
    if not allowed[rows, cols].all():
        return False
    ground = terrain[rows, cols]
    if not np.isfinite(ground).all():
        return False
    prof = z_start_design + ts * (z_end_target - z_start_design)
    if np.max(np.abs(prof - ground)) > max_earthwork:
        return False
    return True


def build_candidate_record(
    candidate_id: str, title: str, subtitle: str, criterion_reason: str,
    route: LineString, start_pt: Point, goal_pt: Point, rotonda: dict,
    sample_fn, boundary_geom, lots_gdf, streams_gdf,
    max_grade: float = 0.10, min_radius_m: float = 15.0,
    platform_m: float = 5.0, carriageway_m: float = 3.5,
    max_earthwork: float = 6.0, max_grade_change: float | None = None,
    dest_mode: str = 'center', search_meta: dict | None = None,
):
    """Sample native DTM, run LP vertical profile optimization, validate platform & watercourses, and return full contract."""
    ss = np.linspace(0.0, route.length, math.ceil(route.length / 2.0) + 1)
    pts = [route.interpolate(float(s)) for s in ss]
    zz = sample_fn(pts)
    if not np.isfinite(zz).all():
        return None
    z0 = float(zz[0])
    z1 = float(zz[-1])
    design = optimize_vertical_profile(ss, zz, z0, z1, max_grade=max_grade,
                                       max_earthwork=max_earthwork, max_grade_change=max_grade_change)
    if design is None:
        return None

    grades = np.diff(design) / np.diff(ss)
    earth = design - zz
    cut = float(np.trapezoid(np.maximum(-earth, 0.0), ss) * platform_m)
    fillv = float(np.trapezoid(np.maximum(earth, 0.0), ss) * platform_m)

    intrusions = [
        dict(
            lote=lot['name'],
            axis_length_m=float(route.intersection(lot.geometry.buffer(-1.0)).length),
            corridor_area_m2=float(route.buffer(platform_m / 2.0).intersection(lot.geometry).area),
        )
        for _, lot in lots_gdf.iterrows()
        if route.buffer(platform_m / 2.0).intersects(lot.geometry)
    ]

    val = validate_platform_and_alignment(
        route, ss, zz, design, sample_fn, boundary_geom, lots_gdf, streams_gdf,
        max_grade=max_grade, min_radius_m=min_radius_m,
        platform_m=platform_m, carriageway_m=carriageway_m
    )
    gstats = compute_grade_statistics(ss, design, zz, max_grade_limit=max_grade)
    wc = val['watercourse_evaluation']

    def to_wgs(g):
        return gpd.GeoSeries([g], crs=32718).to_crs(4326).iloc[0]

    route_wgs = to_wgs(route)
    start_wgs = list(to_wgs(start_pt).coords)[0]
    goal_wgs = list(to_wgs(goal_pt).coords)[0]
    rotonda_center_wgs = list(to_wgs(Point(rotonda['center_utm'])).coords)[0]

    dz_abs = abs(z1 - z0)
    theo_mins = dict(
        at_10_pct_m=round(dz_abs / 0.10, 2),
        at_8_pct_m=round(dz_abs / 0.08, 2),
        at_6_pct_m=round(dz_abs / 0.06, 2),
        at_selected_limit_m=round(dz_abs / max(1e-4, max_grade), 2),
    )

    data = dict(
        id=candidate_id,
        title=title,
        subtitle=subtitle,
        recommendation_criterion=criterion_reason,
        status=STATUS_FEASIBLE if val['all_constraints_satisfied'] else 'FEASIBLE_WITH_FLAGS',
        destination_connection_mode=dest_mode,
        origin='Desembocadura occidental del arroyo ID1, indicada por usuario; no se acredita conexión a camino público',
        rotonda_source=rotonda['source'],
        legacy_roads_used=False,
        road_status='Corredor conceptual, sin proyecto constructivo ni garantía de transitabilidad',
        length_plan_m=float(route.length),
        length_3d_m=float(np.hypot(np.diff(ss), np.diff(design)).sum()),
        start_elevation_m=z0,
        end_elevation_m=z1,
        elevation_gain_m=z1 - z0,
        minimum_length_at_10pct_m=dz_abs / 0.10,
        theoretical_minimum_lengths_m=theo_mins,
        selected_max_grade_limit_pct=round(max_grade * 100.0, 2),
        max_design_grade_pct=float(np.max(np.abs(grades)) * 100.0),
        p95_design_grade_pct=float(np.percentile(np.abs(grades), 95) * 100.0),
        sustained_grade_stats=gstats,
        horizontal_curve_radius_m=float(min_radius_m),
        validated_min_radius_m=val['min_radius_measured_m'],
        carriageway_m=float(carriageway_m),
        platform_m=float(platform_m),
        granular_thickness_m=0.20,
        granular_volume_m3=float(route.length * carriageway_m * 0.2 + math.pi * rotonda['radius_m'] ** 2 * 0.2),
        cut_proxy_m3=cut,
        fill_proxy_m3=fillv,
        earthwork_proxy_total_m3=round(cut + fillv, 1),
        max_vertical_adjustment_m=float(np.max(np.abs(earth))),
        outside_property_axis_m=float(route.difference(boundary_geom).length),
        lot_impacts=intrusions,
        stream_crossings=wc['all_intersections'],
        watercourse_evaluation=wc,
        validation=val,
        search_metadata=search_meta or {},
        suitability_assumptions=dict(
            surface='Carpeta granular compactada mín. 20 cm CBR ≥ 60% sobre subrasante preparada.',
            drainage='Cunetas laterales revestidas/perfiladas, bombeo 3% y alcantarilla en cruce de quebrada ID5.',
            vehicle='Vehículo 2WD liviano con neumáticos en buen estado, velocidad de diseño 10–15 km/h y apartaderos.',
            unknowns='Geotecnia, humedad estacional, espesor de suelo vegetal, nivel freático y presencia de roca no medidos (no inferibles de ortofoto).',
        ),
        start_wgs84=start_wgs,
        goal_wgs84=goal_wgs,
        rotonda_wgs84=rotonda_center_wgs,
        geometry_wgs84=json.loads(gpd.GeoSeries([route_wgs], crs=4326).to_json())['features'][0]['geometry'],
        profile=[
            dict(
                distance_m=float(s),
                terrain_m=float(z),
                design_m=float(v),
                grade_pct=round(float((design[min(i + 1, len(ss) - 1)] - design[max(0, i - 1)]) /
                                      max(1e-6, ss[min(i + 1, len(ss) - 1)] - ss[max(0, i - 1)]) * 100.0), 2),
                cut_fill_m=round(float(v - z), 3),
                lon=round(float(route_wgs.interpolate(float(s) / max(1e-6, route.length), normalized=True).x), 7),
                lat=round(float(route_wgs.interpolate(float(s) / max(1e-6, route.length), normalized=True).y), 7),
            )
            for i, (s, z, v) in enumerate(zip(ss, zz, design))
        ],
    )
    return data, route


def solve_terrain_route(
    start_pt: Point, goal_pt: Point, z0: float, z1: float,
    tr, allowed: np.ndarray, terrain: np.ndarray, cellcost: np.ndarray,
    limit: float = 0.10, earthwork_weight: float = 1.5, turn_penalty: float = 15.0,
    heuristic_weight: float = 8.0, max_states: int = 400000,
    enforce_connector_mask: bool = True, max_earthwork_search: float = 5.5,
):
    """Search for a 3D graded alignment (row, col, heading, design_z) respecting limit and allowed mask."""
    h, w = allowed.shape

    def rc(p):
        return rasterio.transform.rowcol(tr, p.x, p.y)

    def point(r, c):
        return np.array(rasterio.transform.xy(tr, r, c), dtype=float)

    a = rc(start_pt)
    b = rc(goal_pt)
    if not (0 <= a[0] < h and 0 <= a[1] < w and 0 <= b[0] < h and 0 <= b[1] < w):
        return None, 0, STATUS_MISSING_DATA
    if not (np.isfinite(z0) and np.isfinite(z1)):
        return None, 0, STATUS_MISSING_DATA

    moves = [
        (0, 8), (3, 8), (6, 6), (8, 3), (8, 0), (8, -3), (6, -6), (3, -8),
        (0, -8), (-3, -8), (-6, -6), (-8, -3), (-8, 0), (-8, 3), (-6, 6), (-3, 8)
    ]
    origin_level = round(z0 * 2.0)
    distances = {}
    prev = {}
    queue = []
    seen = 0
    for d in range(16):
        key = (*a, d, origin_level)
        distances[key] = 0.0
        heapq.heappush(queue, (0.0, 0.0, key))
    edgecache = {}

    while queue:
        _, cost, key = heapq.heappop(queue)
        if cost > distances.get(key, float('inf')) + 1e-8:
            continue
        r, c, last, kz = key
        zz_design = kz * 0.5
        seen += 1
        distance_goal = math.hypot(r - b[0], c - b[1]) * STEP
        if 2.0 < distance_goal < 22.0 and abs(zz_design - z1) / distance_goal <= limit:
            pp = point(r, c)
            conn_ok = True
            if enforce_connector_mask:
                conn_ok = check_connector_segment(
                    pp, (goal_pt.x, goal_pt.y), tr, allowed, terrain,
                    zz_design, z1, limit, max_earthwork=max_earthwork_search
                )
            if conn_ok:
                keys = [key]
                while keys[-1] in prev:
                    keys.append(prev[keys[-1]])
                keys.reverse()
                coords = [(start_pt.x, start_pt.y)] + [point(k[0], k[1]) for k in keys[1:]] + [(goal_pt.x, goal_pt.y)]
                return coords, seen, STATUS_FEASIBLE

        for delta in (-2, -1, 0, 1, 2):
            d = (last + delta) % 16
            ek = (r, c, d)
            if ek not in edgecache:
                dr, dc = moves[d]
                rr = r + dr
                cc = c + dc
                if not (0 <= rr < h and 0 <= cc < w):
                    edgecache[ek] = None
                else:
                    ts = np.linspace(0.0, 1.0, 9)
                    rs = np.rint(r + ts * dr).astype(int)
                    cs = np.rint(c + ts * dc).astype(int)
                    edgecache[ek] = (
                        (rr, cc, STEP * math.hypot(dr, dc), tuple(float(x) for x in terrain[rs, cs]), float(cellcost[rs, cs].mean()))
                        if allowed[rs, cs].all() else None
                    )
            edge_data = edgecache[ek]
            if edge_data is None:
                continue
            rr, cc, length, ground, costmean = edge_data
            g_end = ground[8]
            low = max(zz_design - limit * length, g_end - 5.0)
            high = min(zz_design + limit * length, g_end + 5.0)
            lo = math.ceil(low * 2.0)
            hi = math.floor(high * 2.0)
            if lo > hi:
                continue
            choices = {lo, hi, max(lo, min(hi, round(g_end * 2.0))), max(lo, min(hi, kz))}
            inv8 = (1.0 / 8.0)
            for nk in choices:
                e = nk * 0.5
                step_z = (e - zz_design) * inv8
                ew_max = 0.0
                ew_sum = 0.0
                for idx9 in range(9):
                    diff = abs((zz_design + idx9 * step_z) - ground[idx9])
                    if diff > ew_max:
                        ew_max = diff
                    ew_sum += diff
                if ew_max > max_earthwork_search:
                    continue
                ew_mean = ew_sum / 9.0
                seg_grade_ratio = abs(e - zz_design) / max(1e-6, length * limit)
                newcost = cost + length * (costmean + ew_mean * earthwork_weight + 0.5 * seg_grade_ratio ** 2) + abs(delta) * turn_penalty
                nextkey = (rr, cc, d, nk)
                if newcost + 1e-8 < distances.get(nextkey, float('inf')):
                    distances[nextkey] = newcost
                    prev[nextkey] = key
                    heuristic = max(math.hypot(rr - b[0], cc - b[1]) * STEP, abs(e - z1) / limit)
                    heapq.heappush(queue, (newcost + heuristic_weight * heuristic, newcost, nextkey))
        if seen > max_states:
            return None, seen, STATUS_EXHAUSTED
    return None, seen, STATUS_INFEASIBLE


def smooth_coords_to_route(coords, radius=RADIUS):
    """Apply corner rounding with iterative pruning of vertices whose adjacent segments are too short for the requested radius."""
    pts = [np.array(p, dtype=float) for p in coords]
    for _ in range(12):
        try:
            return round_corners(pts, radius=radius)
        except ValueError:
            if len(pts) <= 3:
                raise
            # Find the interior vertex where tangent > 0.45 * min(la, lb) and remove the tighter vertex
            removed = False
            for i in range(1, len(pts) - 1):
                a, v, b = pts[i - 1], pts[i], pts[i + 1]
                la = np.linalg.norm(v - a)
                lb = np.linalg.norm(b - v)
                if la < 1e-6 or lb < 1e-6:
                    pts.pop(i)
                    removed = True
                    break
                u = (v - a) / la
                w = (b - v) / lb
                theta = math.acos(float(np.clip(np.dot(u, w), -1.0, 1.0)))
                tangent = radius * math.tan(theta / 2.0)
                if tangent > 0.45 * min(la, lb):
                    # Drop the interior vertex that creates the short leg
                    drop_idx = i if (la <= lb or i == len(pts) - 2) else (i + 1)
                    if drop_idx == len(pts) - 1:
                        drop_idx = i
                    pts.pop(drop_idx)
                    removed = True
                    break
            if not removed:
                break
    return round_corners(pts, radius=radius)


def main():
    all_lots = read_kml(ROOT / '20260408_parelas_caminas_kml.kml').to_crs(32718)
    lots = all_lots[all_lots.name.str.fullmatch(r'\d+')].copy()
    boundary = read_kml(ROOT / '20231207_deslinde_original.kml').to_crs(32718).geometry.union_all()
    streams = gpd.read_file(ROOT / 'hidro.shp').to_crs(32718)
    south = streams[streams.id == 1].geometry.iloc[0]
    # El extremo occidental de ID1 es su desembocadura en el río principal.
    start = Point(min((south.coords[0], south.coords[-1]), key=lambda p: p[0]))
    rotonda = json.loads((OUT / 'rotonda.json').read_text(encoding='utf8'))
    goal_center = Point(rotonda['center_utm'])
    rot_r = float(rotonda['radius_m'])

    with rasterio.open(ROOT / 'LA_CANTINA_dtm.tif') as dem:
        def sample(points):
            return np.array([
                float(v[0]) if (not np.ma.is_masked(v[0]) and float(v[0]) > -9999) else np.nan
                for v in dem.sample([(p.x, p.y) for p in points], masked=True)
            ])

        z0, z1 = map(float, sample([start, goal_center]))
        print('Acceso/rotonda', z0, z1, 'mínimo teórico a 10%', abs(z1 - z0) / 0.1, flush=True)
        left = dem.bounds.left
        top = dem.bounds.top
        w = math.ceil((dem.bounds.right - left) / STEP)
        h = math.ceil((top - dem.bounds.bottom) / STEP)
        tr = from_origin(left, top, STEP, STEP)
        grid = np.full((h, w), np.nan, dtype='float32')
        reproject(
            dem.read(1), grid,
            src_transform=dem.transform, src_crs=dem.crs, src_nodata=dem.nodata,
            dst_transform=tr, dst_crs=dem.crs, dst_nodata=np.nan, resampling=Resampling.bilinear
        )
        valid = np.isfinite(grid) & (grid > -9999)
        grid[~valid] = np.nan
        fill = grid.copy()
        inds = distance_transform_edt(~valid, return_distances=False, return_indices=True)
        fill[~valid] = grid[tuple(inds[:, ~valid])]
        terrain = gaussian_filter(fill, 2.0)  # sólo para búsqueda; perfil final DTM nativo.
        inside = rasterize([(boundary, 1)], out_shape=(h, w), transform=tr).astype(bool)
        allowed = valid & inside
        # Evita cruzar el arroyo permanente sur salvo la conexión del origen.
        water_buffer = south.buffer(4.0).difference(start.buffer(8.0))
        water_mask = rasterize([(water_buffer, 1)], out_shape=(h, w), transform=tr).astype(bool)
        allowed &= ~water_mask
        # Se permite afectar linderos; se penaliza cruzar por centro de lotes.
        inner = rasterize([(p.buffer(-6.0), 1) for p in lots.geometry], out_shape=(h, w), transform=tr).astype(bool)
        gy, gx = np.gradient(terrain, STEP)
        side = np.hypot(gx, gy)
        cellcost_base = 1.0 + inner * 4.0 + np.maximum(side - 0.20, 0.0) * 8.0

        def rc(p):
            return rasterio.transform.rowcol(tr, p.x, p.y)

        def point(r, c):
            return np.array(rasterio.transform.xy(tr, r, c))

        a, b = rc(start), rc(goal_center)
        allowed[a] = True
        allowed[b] = True
        moves = [
            (0, 8), (3, 8), (6, 6), (8, 3), (8, 0), (8, -3), (6, -6), (3, -8),
            (0, -8), (-3, -8), (-6, -6), (-8, -3), (-8, 0), (-8, 3), (-6, 6), (-3, 8)
        ]

        # 1. Exact Baseline (Revision 3 compatibility: 660.11 m to roundabout center)
        def solve_baseline_exact(limit=0.10):
            origin_level = round(z0 * 2)
            distances = {}
            prev = {}
            queue = []
            seen = 0
            for d in range(16):
                key = (*a, d, origin_level)
                distances[key] = 0
                heapq.heappush(queue, (0.0, 0.0, key))
            edgecache = {}
            while queue:
                _, cost, key = heapq.heappop(queue)
                if cost > distances.get(key, float('inf')) + 1e-8:
                    continue
                r, c, last, kz = key
                zz_design = kz * 0.5
                seen += 1
                distance_goal = math.hypot(r - b[0], c - b[1]) * STEP
                if 2 < distance_goal < 22 and abs(zz_design - z1) / distance_goal <= limit:
                    keys = [key]
                    while keys[-1] in prev:
                        keys.append(prev[keys[-1]])
                    keys.reverse()
                    coords = [(start.x, start.y)] + [point(k[0], k[1]) for k in keys[1:]] + [(goal_center.x, goal_center.y)]
                    return coords, seen
                for delta in (-2, -1, 0, 1, 2):
                    d = (last + delta) % 16
                    ek = (r, c, d)
                    if ek not in edgecache:
                        dr, dc = moves[d]
                        rr = r + dr
                        cc = c + dc
                        if not (0 <= rr < h and 0 <= cc < w):
                            edgecache[ek] = None
                        else:
                            ts = np.linspace(0, 1, 9)
                            rs = np.rint(r + ts * dr).astype(int)
                            cs = np.rint(c + ts * dc).astype(int)
                            edgecache[ek] = (
                                (rr, cc, STEP * math.hypot(dr, dc), tuple(float(x) for x in terrain[rs, cs]), float(cellcost_base[rs, cs].mean()))
                                if allowed[rs, cs].all() else None
                            )
                    edge_data = edgecache[ek]
                    if edge_data is None:
                        continue
                    rr, cc, length, ground, costmean = edge_data
                    g_end = ground[8]
                    low = max(zz_design - limit * length, g_end - 5.0)
                    high = min(zz_design + limit * length, g_end + 5.0)
                    lo = math.ceil(low * 2)
                    hi = math.floor(high * 2)
                    if lo > hi:
                        continue
                    choices = {lo, hi, max(lo, min(hi, round(g_end * 2))), max(lo, min(hi, kz))}
                    inv8 = (1.0 / 8.0)
                    for nk in choices:
                        e = nk * 0.5
                        step_z = (e - zz_design) * inv8
                        ew_max = 0.0
                        ew_sum = 0.0
                        for idx9 in range(9):
                            diff = abs((zz_design + idx9 * step_z) - ground[idx9])
                            if diff > ew_max:
                                ew_max = diff
                            ew_sum += diff
                        if ew_max > 5.5:
                            continue
                        newcost = cost + length * (costmean + (ew_sum / 9.0) * 1.5) + abs(delta) * 15
                        nextkey = (rr, cc, d, nk)
                        if newcost + 1e-8 < distances.get(nextkey, float('inf')):
                            distances[nextkey] = newcost
                            prev[nextkey] = key
                            heuristic = max(math.hypot(rr - b[0], cc - b[1]) * STEP, abs(e - z1) / limit)
                            heapq.heappush(queue, (newcost + 8 * heuristic, newcost, nextkey))
                if seen > 400000:
                    break
            return None, seen

        base_coords, base_seen = solve_baseline_exact(0.10)
        if base_coords is None:
            raise RuntimeError('No se encontró trazado base.')
        try:
            base_route = round_corners(base_coords, radius=RADIUS)
        except ValueError:
            pruned_base = [
                p for i, p in enumerate(base_coords)
                if i == 0 or i == len(base_coords) - 1 or (
                    np.linalg.norm(np.array(p) - np.array(base_coords[-1])) > 24 and
                    np.linalg.norm(np.array(p) - np.array(base_coords[0])) > 24
                )
            ]
            base_route = round_corners(pruned_base, radius=RADIUS)
        base_data, base_route = build_candidate_record(
            candidate_id='baseline_10pct',
            title='Trazado Base (Rev. 3 · ≤10%)',
            subtitle='660 m en planta · conexión al centro de rotonda · R15 m',
            criterion_reason='Línea base de referencia (Revisión 3) desde desembocadura ID1 hasta el centro de la rotonda inferida.',
            route=base_route, start_pt=start, goal_pt=goal_center, rotonda=rotonda,
            sample_fn=sample, boundary_geom=boundary, lots_gdf=lots, streams_gdf=streams,
            max_grade=0.10, min_radius_m=RADIUS, platform_m=5.0, carriageway_m=3.5,
            dest_mode='center',
            search_meta=dict(algorithm='weighted_astar_3d', heuristic_weight=8.0, states_explored=base_seen, grade_limit_pct=10.0),
        )

        # Write baseline outputs for full backwards compatibility with verify_planning.py
        (OUT / 'camino_propuesto.json').write_text(json.dumps(base_data, ensure_ascii=False, indent=2), encoding='utf8')
        features = [
            dict(name='Acceso nuevo 2WD · conceptual', geometry=base_route),
            dict(name='Inicio: desembocadura sur', geometry=start),
            dict(name='Rotonda objetivo inferida del loteo', geometry=goal_center),
            dict(name='Plataforma conceptual 5 m', geometry=base_route.buffer(2.5)),
            dict(name='Rotonda conceptual', geometry=goal_center.buffer(rotonda['radius_m'])),
        ]
        gpd.GeoDataFrame(features, crs=32718).to_crs(4326).to_file(OUT / 'camino_propuesto.geojson', driver='GeoJSON')
        with (OUT / 'perfil_camino.csv').open('w', newline='', encoding='utf-8-sig') as f:
            wr = csv.DictWriter(f, fieldnames=['distance_m', 'terrain_m', 'design_m'])
            wr.writeheader()
            wr.writerows([dict(distance_m=p['distance_m'], terrain_m=p['terrain_m'], design_m=p['design_m']) for p in base_data['profile']])

        # 2. Generate distinct, validated comparison candidates connecting to the inferred roundabout perimeter
        candidates = [base_data]
        cand_features = [
            dict(candidate_id=base_data['id'], title=base_data['title'], max_grade_pct=10.0,
                 length_plan_m=base_data['length_plan_m'], geometry=base_route)
        ]

        # Western / WNW perimeter of the inferred roundabout has lower natural elevation (407.4-409.4 m vs 411.3 m center)
        perim_angle_rad = math.radians(180.0)
        goal_perim = Point(
            goal_center.x + rot_r * math.cos(perim_angle_rad),
            goal_center.y + rot_r * math.sin(perim_angle_rad)
        )
        r_perim, c_perim = rc(goal_perim)
        allowed[r_perim, c_perim] = True
        z_perim = float(sample([goal_perim])[0])

        perim_nw_rad = math.radians(165.0)
        goal_perim_nw = Point(
            goal_center.x + rot_r * math.cos(perim_nw_rad),
            goal_center.y + rot_r * math.sin(perim_nw_rad)
        )
        r_pnw, c_pnw = rc(goal_perim_nw)
        allowed[r_pnw, c_pnw] = True
        z_perim_nw = float(sample([goal_perim_nw])[0])

        # Candidate A: Shorter alignment to roundabout western perimeter (<=10% grade)
        cellcost_short = 1.0 + inner * 3.0 + np.maximum(side - 0.22, 0.0) * 7.0
        coords_short, seen_short, status_short = solve_terrain_route(
            start, goal_perim, z0, z_perim, tr, allowed, terrain, cellcost_short,
            limit=0.10, earthwork_weight=1.3, turn_penalty=14.0, heuristic_weight=8.0,
            max_states=60000, enforce_connector_mask=True
        )
        if coords_short is not None:
            r_short = smooth_coords_to_route(coords_short, radius=15.0)
            rec_short = build_candidate_record(
                candidate_id='short_perim_10pct',
                title='Alternativa A · Empalme oeste más corto (≤10%)',
                subtitle='Conecta al perímetro occidental de la rotonda (cota 409,4 m) · R15 m',
                criterion_reason='Empalma en el borde oeste de la rotonda inferida (r=25,98 m, cota 409,4 m en vez de 411,3 m en el centro), reduciendo desnivel y longitud horizontal.',
                route=r_short, start_pt=start, goal_pt=goal_perim, rotonda=rotonda,
                sample_fn=sample, boundary_geom=boundary, lots_gdf=lots, streams_gdf=streams,
                max_grade=0.10, min_radius_m=15.0, platform_m=5.0, carriageway_m=3.5,
                dest_mode='perimeter_180deg',
                search_meta=dict(algorithm='weighted_astar_3d', heuristic_weight=8.0, states_explored=seen_short, grade_limit_pct=10.0),
            )
            if rec_short is not None:
                c_data, c_geom = rec_short
                candidates.append(c_data)
                cand_features.append(dict(candidate_id=c_data['id'], title=c_data['title'], max_grade_pct=10.0,
                                          length_plan_m=c_data['length_plan_m'], geometry=c_geom))

        # Candidate B: Gentler sustained climb (<= 9.0% propagated through search AND LP!)
        for gentle_limit, cid, label_pct in [(0.09, 'gentle_9pct', '9,0%'), (0.092, 'gentle_9_2pct', '9,2%')]:
            cellcost_gentle = 1.0 + inner * 3.0 + np.maximum(side - 0.20, 0.0) * 7.0
            coords_g, seen_g, status_g = solve_terrain_route(
                start, goal_perim_nw, z0, z_perim_nw, tr, allowed, terrain, cellcost_gentle,
                limit=gentle_limit, earthwork_weight=1.4, turn_penalty=14.0, heuristic_weight=8.0,
                max_states=60000, enforce_connector_mask=True, max_earthwork_search=5.6
            )
            if coords_g is not None:
                try:
                    r_g = smooth_coords_to_route(coords_g, radius=15.0)
                    rec_g = build_candidate_record(
                        candidate_id=cid,
                        title=f'Alternativa B · Ascenso más tendido (≤{label_pct})',
                        subtitle=f'Pendiente máxima {label_pct} en todo el perfil · empalme NO (407,4 m) · R15 m',
                        criterion_reason=f'Reduce la pendiente máxima y sostenida a ≤{label_pct} (0 m al 10%) conectando al arco noroeste de menor cota de la rotonda.',
                        route=r_g, start_pt=start, goal_pt=goal_perim_nw, rotonda=rotonda,
                        sample_fn=sample, boundary_geom=boundary, lots_gdf=lots, streams_gdf=streams,
                        max_grade=gentle_limit, min_radius_m=15.0, platform_m=5.0, carriageway_m=3.5,
                        max_earthwork=6.0, dest_mode='perimeter_165deg',
                        search_meta=dict(algorithm='weighted_astar_3d', heuristic_weight=8.0, states_explored=seen_g, grade_limit_pct=gentle_limit * 100.0),
                    )
                    if rec_g is not None:
                        c_data, c_geom = rec_g
                        candidates.append(c_data)
                        cand_features.append(dict(candidate_id=c_data['id'], title=c_data['title'], max_grade_pct=gentle_limit * 100.0,
                                                  length_plan_m=c_data['length_plan_m'], geometry=c_geom))
                        break
                except Exception as exc:
                    print('Gentle candidate exception:', gentle_limit, exc)

        # Candidate C: Lower earthwork proxy & lower parcel interior intrusion
        cellcost_low_impact = 1.0 + inner * 14.0 + np.maximum(side - 0.18, 0.0) * 12.0
        coords_li, seen_li, status_li = solve_terrain_route(
            start, goal_perim_nw, z0, z_perim_nw, tr, allowed, terrain, cellcost_low_impact,
            limit=0.10, earthwork_weight=3.8, turn_penalty=16.0, heuristic_weight=8.0,
            max_states=60000, enforce_connector_mask=True, max_earthwork_search=5.5
        )
        if coords_li is not None:
            try:
                r_li = smooth_coords_to_route(coords_li, radius=15.0)
                rec_li = build_candidate_record(
                    candidate_id='low_impact_10pct',
                    title='Alternativa C · Menor corte/relleno y linderos',
                    subtitle='Se ciñe más a cotas naturales y bordes de lotes · R15 m',
                    criterion_reason='Penaliza fuertemente el movimiento de tierra vertical y la intrusión al interior de lotes subdivididos.',
                    route=r_li, start_pt=start, goal_pt=goal_perim_nw, rotonda=rotonda,
                    sample_fn=sample, boundary_geom=boundary, lots_gdf=lots, streams_gdf=streams,
                    max_grade=0.10, min_radius_m=15.0, platform_m=5.0, carriageway_m=3.5,
                    max_earthwork=6.0, dest_mode='perimeter_165deg',
                    search_meta=dict(algorithm='weighted_astar_3d', heuristic_weight=8.0, states_explored=seen_li, grade_limit_pct=10.0),
                )
                if rec_li is not None:
                    c_data, c_geom = rec_li
                    candidates.append(c_data)
                    cand_features.append(dict(candidate_id=c_data['id'], title=c_data['title'], max_grade_pct=10.0,
                                              length_plan_m=c_data['length_plan_m'], geometry=c_geom))
            except Exception as exc:
                print('Low impact candidate exception:', exc)

        bundle = dict(
            selected_id='baseline_10pct',
            rotonda=dict(
                center_utm=rotonda['center_utm'],
                center_wgs84=base_data['rotonda_wgs84'],
                radius_m=rotonda['radius_m'],
                boundary_vertices_matched=rotonda['boundary_vertices_matched'],
                source=rotonda['source'],
            ),
            origin_baseline=dict(
                label='Inicio actual: desembocadura ID1',
                utm=[start.x, start.y],
                wgs84=base_data['start_wgs84'],
                elevation_m=z0,
                note='Punto en desembocadura occidental del arroyo ID1; no acredita empalme a camino público ni puente.',
            ),
            candidates=candidates,
        )
        (OUT / 'caminos_candidatos.json').write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf8')
        gpd.GeoDataFrame(cand_features, crs=32718).to_crs(4326).to_file(OUT / 'caminos_candidatos.geojson', driver='GeoJSON')
        print('Candidatos viales generados:', [(c['id'], round(c['length_plan_m'], 1), c['max_design_grade_pct'], round(c['earthwork_proxy_total_m3'], 0)) for c in candidates], flush=True)


if __name__ == '__main__':
    main()
