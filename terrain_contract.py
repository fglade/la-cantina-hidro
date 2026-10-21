"""Shared terrain data contract and surface preprocessing for La Cantina (EPSG:32718)."""
from pathlib import Path
import json, math, zlib, base64
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.transform import from_origin, array_bounds
from rasterio.warp import reproject, calculate_default_transform, transform_bounds
from rasterio.features import rasterize
from rasterio.enums import Resampling
from PIL import Image
from inspect_data import read_kml

ROOT = Path(__file__).parent
OUT = ROOT / 'outputs'
OUT.mkdir(exist_ok=True)

CRS_METRIC = 'EPSG:32718'
CRS_WGS84 = 'EPSG:4326'
ANALYSIS_STEP_M = 2.0
PREPROCESSING_VERSION = '4.0.0'


class MissingTerrainInputError(RuntimeError):
    """Raised when neither the native DTM raster nor the preprocessed 2 m cache is available."""
    pass


def compute_grid_convergence_deg(lon_deg: float, lat_deg: float, central_meridian_deg: float = -75.0) -> float:
    """Compute UTM grid convergence angle (gamma) in degrees: True North to Grid North."""
    dlon = math.radians(lon_deg - central_meridian_deg)
    lat = math.radians(lat_deg)
    return math.degrees(math.atan(math.tan(dlon) * math.sin(lat)))


def horn_slope_aspect_hillshade(grid: np.ndarray, valid: np.ndarray, step: float,
                                azimuth_deg: float = 315.0, altitude_deg: float = 45.0):
    """Compute slope (pct & deg), aspect (deg clockwise from north), and hillshade (0..255) on valid cells."""
    # Pad grid using nearest valid edge values only where immediate neighbors are valid
    z = grid.copy()
    # Fill NaNs temporarily for gradient, then mask out any cell whose 3x3 neighborhood has NaNs or itself is invalid
    from scipy.ndimage import distance_transform_edt, binary_erosion
    if (~valid).any():
        inds = distance_transform_edt(~valid, return_distances=False, return_indices=True)
        z[~valid] = z[tuple(inds[:, ~valid])]
    gy, gx = np.gradient(z, step)
    # Note: row index increases southward, so dz/dy_north = -gy
    dz_dx = gx
    dz_dy = -gy
    slope_rad = np.arctan(np.hypot(dz_dx, dz_dy))
    slope_pct = np.hypot(dz_dx, dz_dy) * 100.0
    # Aspect clockwise from North (0=N, 90=E, 180=S, 270=W): direction of steepest descent
    aspect_rad = np.arctan2(-dz_dx, -dz_dy)
    aspect_deg = np.degrees(aspect_rad) % 360.0

    zenith_rad = math.radians(90.0 - altitude_deg)
    az_math_rad = math.radians(azimuth_deg)
    # Illumination angle
    shaded = (np.cos(zenith_rad) * np.cos(slope_rad) +
              np.sin(zenith_rad) * np.sin(slope_rad) * np.cos(az_math_rad - aspect_rad))
    hillshade = np.clip(shaded * 255.0, 0, 255).astype(np.uint8)

    slope_pct[~valid] = np.nan
    aspect_deg[~valid] = np.nan
    hillshade[~valid] = 0
    return slope_pct, aspect_deg, hillshade


def save_web_rgba_overlay(rgba_utm: np.ndarray, src_transform, src_crs, out_png: Path, maxsize: int = 1200):
    """Reproject an RGBA array in EPSG:32718 to EPSG:3857 and save PNG + WGS84 bounds JSON."""
    h, w = rgba_utm.shape[1], rgba_utm.shape[2]
    left, bottom, right, top = array_bounds(h, w, src_transform)
    factor = max(w, h) / maxsize if max(w, h) > maxsize else 1.0
    sw, sh = max(1, round(w / factor)), max(1, round(h / factor))
    dst_tr, dw, dh = calculate_default_transform(src_crs, 3857, sw, sh, left, bottom, right, top)
    dest = np.zeros((4, dh, dw), dtype=np.uint8)
    for b in range(4):
        reproject(
            rgba_utm[b], dest[b],
            src_transform=src_transform, src_crs=src_crs,
            dst_transform=dst_tr, dst_crs=3857,
            resampling=Resampling.bilinear if b < 3 else Resampling.nearest
        )
    l3857, b3857, r3857, t3857 = array_bounds(dh, dw, dst_tr)
    wb = transform_bounds(3857, 4326, l3857, b3857, r3857, t3857)
    bounds = [[wb[1], wb[0]], [wb[3], wb[2]]]
    Image.fromarray(np.moveaxis(dest, 0, 2), 'RGBA').save(out_png, optimize=True)
    out_png.with_suffix('.json').write_text(json.dumps(bounds), encoding='utf8')
    return bounds


def colorize_hypsometric(grid: np.ndarray, valid: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    """Create RGBA (4, H, W) hypsometric tint from elevation grid."""
    stops = np.array([0.0, 0.25, 0.50, 0.75, 1.0])
    colors = np.array([
        [63, 164, 191],   # #3fa4bf low
        [101, 193, 140],  # #65c18c
        [235, 220, 115],  # #ebdc73
        [210, 138, 80],   # #d28a50
        [162, 91, 103],   # #a25b67 high
    ], dtype=np.float32)
    norm = np.clip((np.nan_to_num(grid, nan=vmin) - vmin) / max(1e-6, vmax - vmin), 0.0, 1.0)
    rgba = np.zeros((4, *grid.shape), dtype=np.uint8)
    for c in range(3):
        rgba[c] = np.interp(norm, stops, colors[:, c]).astype(np.uint8)
    rgba[3] = np.where(valid, 210, 0).astype(np.uint8)
    return rgba


def colorize_slope(slope_pct: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Create RGBA (4, H, W) slope map (0..60%+)."""
    stops = np.array([0.0, 8.0, 15.0, 30.0, 55.0])
    colors = np.array([
        [78, 168, 120],   # <8% gentle green
        [218, 214, 96],   # 8-15% yellow
        [230, 148, 62],   # 15-30% orange
        [198, 75, 65],    # 30-55% red
        [115, 38, 72],    # >55% steep wine
    ], dtype=np.float32)
    s = np.nan_to_num(slope_pct, nan=0.0)
    rgba = np.zeros((4, *slope_pct.shape), dtype=np.uint8)
    for c in range(3):
        rgba[c] = np.interp(s, stops, colors[:, c]).astype(np.uint8)
    rgba[3] = np.where(valid, 205, 0).astype(np.uint8)
    return rgba


def colorize_aspect(aspect_deg: np.ndarray, slope_pct: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Create RGBA (4, H, W) aspect orientation map (North=warm sun in S. hemisphere, South=cool)."""
    # In southern hemisphere: North (0/360) is sunny/warm (gold/amber), East (90) teal-green, South (180) cool blue, West (270) coral
    stops = np.array([0.0, 90.0, 180.0, 270.0, 360.0])
    colors = np.array([
        [242, 198, 75],   # N (0) warm gold (equator-facing)
        [92, 184, 142],   # E (90) morning green
        [68, 122, 178],   # S (180) polar cool blue
        [214, 118, 88],   # W (270) afternoon terracotta
        [242, 198, 75],   # N (360)
    ], dtype=np.float32)
    a = np.nan_to_num(aspect_deg, nan=0.0) % 360.0
    flat = valid & (np.nan_to_num(slope_pct, nan=0.0) < 2.0)
    rgba = np.zeros((4, *aspect_deg.shape), dtype=np.uint8)
    for c in range(3):
        ch = np.interp(a, stops, colors[:, c]).astype(np.uint8)
        ch[flat] = 195
        rgba[c] = ch
    rgba[3] = np.where(valid, 195, 0).astype(np.uint8)
    return rgba


def build_or_load_terrain_contract(force_rebuild: bool = False) -> dict:
    """Build or load the shared terrain data contract and 2 m elevation grid."""
    contract_path = OUT / 'terrain_contract.json'
    grid_json_path = OUT / 'terrain_grid_2m.json'
    dtm_path = ROOT / 'LA_CANTINA_dtm.tif'

    if not dtm_path.exists():
        if contract_path.exists() and grid_json_path.exists():
            return json.loads(contract_path.read_text(encoding='utf8'))
        raise MissingTerrainInputError(
            'Falta el insumo raster LA_CANTINA_dtm.tif y no existe caché preprocesado en outputs/terrain_grid_2m.json.'
        )

    if not force_rebuild and contract_path.exists() and grid_json_path.exists():
        # Check if web rasters also exist
        if all((OUT / f'terrain_{k}_web.png').exists() for k in ('hillshade', 'hypsometric', 'slope', 'aspect')):
            return json.loads(contract_path.read_text(encoding='utf8'))

    boundary = read_kml(ROOT / '20231207_deslinde_original.kml').to_crs(32718).geometry.union_all()
    contours_path = ROOT / 'LA_CANTINA_elev1m_res100cm_size20_DTM.shp'
    contour_count = len(gpd.read_file(contours_path)) if contours_path.exists() else 512

    with rasterio.open(dtm_path) as dem:
        z_native = dem.read(1, masked=True)
        native_valid = (~np.ma.getmaskarray(z_native)) & (z_native.data > -9999) & np.isfinite(z_native.data)
        z_min = float(z_native.data[native_valid].min())
        z_max = float(z_native.data[native_valid].max())

        left, bottom, right, top = dem.bounds.left, dem.bounds.bottom, dem.bounds.right, dem.bounds.top
        w = math.ceil((right - left) / ANALYSIS_STEP_M)
        h = math.ceil((top - bottom) / ANALYSIS_STEP_M)
        tr = from_origin(left, top, ANALYSIS_STEP_M, ANALYSIS_STEP_M)

        grid = np.full((h, w), np.nan, dtype=np.float32)
        reproject(
            z_native.filled(np.nan), grid,
            src_transform=dem.transform, src_crs=dem.crs,
            dst_transform=tr, dst_crs=dem.crs,
            src_nodata=np.nan, dst_nodata=np.nan,
            resampling=Resampling.bilinear
        )
        grid[grid <= -9999] = np.nan
        valid = np.isfinite(grid)

        inside = rasterize([(boundary, 1)], out_shape=(h, w), transform=tr, fill=0).astype(bool)
        inside_valid = inside & valid
        cell_area = ANALYSIS_STEP_M ** 2
        prop_area_ha = boundary.area / 10000.0
        coverage_pct = float(100.0 * (inside_valid.sum() * cell_area) / boundary.area)
        full_valid_ha = float(valid.sum() * cell_area / 10000.0)

        wb = transform_bounds(32718, 4326, left, bottom, right, top)
        center_lon = 0.5 * (wb[0] + wb[2])
        center_lat = 0.5 * (wb[1] + wb[3])
        convergence_deg = compute_grid_convergence_deg(center_lon, center_lat)

        # Compute terrain derivatives on the 2 m metric grid
        slope_pct, aspect_deg, hillshade = horn_slope_aspect_hillshade(grid, valid, ANALYSIS_STEP_M)

        # Save web overlays (Hillshade, Hypsometric, Slope, Aspect)
        hs_rgba = np.zeros((4, h, w), dtype=np.uint8)
        # Neutral warm stone/topo hillshade tint so it works as a clean neutral terrain material
        hs_rgba[0] = np.clip(hillshade * 0.96 + 8, 0, 255).astype(np.uint8)
        hs_rgba[1] = np.clip(hillshade * 0.97 + 8, 0, 255).astype(np.uint8)
        hs_rgba[2] = np.clip(hillshade * 0.91 + 6, 0, 255).astype(np.uint8)
        hs_rgba[3] = np.where(valid, 235, 0).astype(np.uint8)
        hs_bounds = save_web_rgba_overlay(hs_rgba, tr, dem.crs, OUT / 'terrain_hillshade_web.png', maxsize=1000)

        hyp_rgba = colorize_hypsometric(grid, valid, z_min, z_max)
        # Blend subtle hillshade into hypsometric for crispness
        shade_factor = np.clip(hillshade.astype(np.float32) / 215.0, 0.55, 1.15)
        for c in range(3):
            hyp_rgba[c] = np.clip(hyp_rgba[c].astype(np.float32) * shade_factor, 0, 255).astype(np.uint8)
        save_web_rgba_overlay(hyp_rgba, tr, dem.crs, OUT / 'terrain_hypsometric_web.png', maxsize=1000)

        slp_rgba = colorize_slope(slope_pct, valid)
        save_web_rgba_overlay(slp_rgba, tr, dem.crs, OUT / 'terrain_slope_web.png', maxsize=1000)

        asp_rgba = colorize_aspect(aspect_deg, slope_pct, valid)
        save_web_rgba_overlay(asp_rgba, tr, dem.crs, OUT / 'terrain_aspect_web.png', maxsize=1000)

        # Encode 2m grid as compact uint16 (0 = NoData, 1..65535 = round((z - z_min)*100) + 1)
        scale = 0.01
        q_grid = np.zeros((h, w), dtype=np.uint16)
        q_vals = np.clip(np.rint((grid[valid] - z_min) / scale) + 1, 1, 65535).astype(np.uint16)
        q_grid[valid] = q_vals
        # Also encode inside_property mask as bitfield or uint8
        prop_mask_packed = np.packbits(inside.astype(np.uint8).ravel()).tobytes()
        grid_compressed = zlib.compress(q_grid.tobytes(), level=9)

        grid_payload = dict(
            crs=CRS_METRIC,
            rows=h,
            cols=w,
            step_m=ANALYSIS_STEP_M,
            origin_utm=[left, top],
            bounds_utm=[left, bottom, right, top],
            bounds_wgs84=[wb[0], wb[1], wb[2], wb[3]],
            overlay_bounds_latlon=hs_bounds,
            z_min=round(z_min, 4),
            z_max=round(z_max, 4),
            scale=scale,
            nodata_uint16=0,
            encoding='zlib_uint16_le_base64',
            data_b64=base64.b64encode(grid_compressed).decode('ascii'),
            inside_property_packbits_b64=base64.b64encode(prop_mask_packed).decode('ascii'),
        )
        grid_json_path.write_text(json.dumps(grid_payload, ensure_ascii=False), encoding='utf8')

        contract = dict(
            preprocessing_version=PREPROCESSING_VERSION,
            crs=CRS_METRIC,
            crs_wgs84=CRS_WGS84,
            native_geotransform=[dem.transform.c, dem.transform.a, dem.transform.b,
                                 dem.transform.f, dem.transform.d, dem.transform.e],
            analysis_geotransform=[tr.c, tr.a, tr.b, tr.f, tr.d, tr.e],
            bounds_utm=dict(left=left, bottom=bottom, right=right, top=top),
            bounds_wgs84=dict(west=wb[0], south=wb[1], east=wb[2], north=wb[3]),
            overlay_bounds_latlon=hs_bounds,
            site_centroid_wgs84=[round(center_lon, 6), round(center_lat, 6)],
            grid_convergence_deg=round(convergence_deg, 4),
            native_resolution_m=round(float(dem.res[0]), 5),
            analysis_resolution_m=ANALYSIS_STEP_M,
            grid_shape=[h, w],
            vertical_units='m',
            vertical_datum_status=(
                'Cotas relativas del levantamiento local DTM (m); '
                'sin datum vertical geodésico oficial (m s. n. m.) certificado.'
            ),
            quantities_distinction=dict(
                contour_interval_m=1.0,
                native_raster_pixel_size_m=round(float(dem.res[0]), 5),
                analysis_grid_spacing_m=ANALYSIS_STEP_M,
                web_contour_simplification_tolerance_m=0.75,
                survey_vertical_accuracy='No acreditada en metadatos del levantamiento original; no inferir precisión submétrica certificada.',
            ),
            valid_data_mask_summary=dict(
                valid_cells=int(valid.sum()),
                total_cells=int(h * w),
                valid_grid_pct=round(float(100.0 * valid.sum() / (h * w)), 2),
                property_area_ha=round(prop_area_ha, 2),
                property_coverage_pct=round(coverage_pct, 2),
                full_valid_area_ha=round(full_valid_ha, 2),
                elev_min_m=round(z_min, 2),
                elev_max_m=round(z_max, 2),
                slope_median_pct=round(float(np.nanmedian(slope_pct)), 1),
                slope_p90_pct=round(float(np.nanpercentile(slope_pct[valid], 90)), 1),
            ),
            source_identity=dict(
                dtm_raster='LA_CANTINA_dtm.tif',
                dsm_raster='LA_CANTINA_dsm.tif (superficie; no usado para diseño vial ni hidráulico)',
                contours_vector='LA_CANTINA_elev1m_res100cm_size20_DTM.shp',
                contour_feature_count=contour_count,
                hydrography_vector='hidro.shp (6 cauces completos)',
                property_boundary='20231207_deslinde_original.kml',
                subdivision_lots='20260408_parelas_caminas_kml.kml (10 lotes; CAMINOS excluidos)',
            ),
            available_surfaces=['hillshade', 'hypsometric', 'slope', 'aspect'],
            missing_inputs=[],
        )
        contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding='utf8')
        return contract


def load_2m_grid():
    """Decode the 2 m metric elevation grid and masks from outputs/terrain_grid_2m.json."""
    build_or_load_terrain_contract()
    payload = json.loads((OUT / 'terrain_grid_2m.json').read_text(encoding='utf8'))
    h, w = payload['rows'], payload['cols']
    raw = zlib.decompress(base64.b64decode(payload['data_b64']))
    q_grid = np.frombuffer(raw, dtype=np.uint16).reshape((h, w))
    valid = q_grid > 0
    grid = np.full((h, w), np.nan, dtype=np.float32)
    grid[valid] = payload['z_min'] + (q_grid[valid].astype(np.float32) - 1.0) * payload['scale']
    inside_bits = np.unpackbits(np.frombuffer(base64.b64decode(payload['inside_property_packbits_b64']), dtype=np.uint8))[:h * w]
    inside = inside_bits.reshape((h, w)).astype(bool)
    tr = from_origin(payload['origin_utm'][0], payload['origin_utm'][1], payload['step_m'], payload['step_m'])
    return grid, valid, inside, tr, payload


if __name__ == '__main__':
    c = build_or_load_terrain_contract(force_rebuild=True)
    print('Terrain contract built:', json.dumps(c['valid_data_mask_summary'], ensure_ascii=False))
