"""Construye index.html Folium con datos, imágenes WebP optimizadas, grilla DTM 2 m y KMZ incorporados."""
from pathlib import Path
import json, base64, io, zipfile, html, shutil, math
import xml.etree.ElementTree as ET
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject, transform_bounds
from PIL import Image
import folium
from folium.plugins import MeasureControl, Fullscreen, MousePosition
from branca.colormap import LinearColormap
from branca.element import MacroElement, Template
from hydraulics import ETA, CAPACITY_FACTOR, HW_C, MINOR_K

ROOT = Path(__file__).parent
OUT = ROOT / 'outputs'
DIST = ROOT / 'sites/la-cantina-hidro/dist'
DIST.mkdir(parents=True, exist_ok=True)
(DIST / 'outputs').mkdir(parents=True, exist_ok=True)


def png_overlay(path, maxsize=1400):
    cache = OUT / (path.stem + '_web.png')
    meta = cache.with_suffix('.json')
    webp_cache = cache.with_suffix('.webp')
    if cache.exists() and meta.exists():
        if not webp_cache.exists():
            Image.open(cache).save(webp_cache, 'WEBP', quality=82, method=4)
        return cache, webp_cache, json.loads(meta.read_text())
    if not path.exists():
        raise FileNotFoundError(f'Falta insumo raster {path} y no existe caché en {cache}')
    with rasterio.open(path) as src:
        factor = max(src.width, src.height) / maxsize
        sw, sh = round(src.width / factor), round(src.height / factor)
        arr = src.read(out_shape=(src.count, sh, sw), resampling=Resampling.bilinear)
        src_tr = src.transform * src.transform.scale(src.width / sw, src.height / sh)
        dst_tr, dw, dh = calculate_default_transform(src.crs, 3857, sw, sh, *src.bounds)
        dest = np.zeros((4, dh, dw), dtype='uint8')
        for b in range(min(4, src.count)):
            reproject(arr[b], dest[b], src_transform=src_tr, src_crs=src.crs, dst_transform=dst_tr, dst_crs=3857, resampling=Resampling.bilinear)
        if src.count < 4:
            dest[3] = 255
        left, bot, right, top = rasterio.transform.array_bounds(dh, dw, dst_tr)
        wb = transform_bounds(3857, 4326, left, bot, right, top)
        bounds = [[wb[1], wb[0]], [wb[3], wb[2]]]
        im = Image.fromarray(np.moveaxis(dest, 0, 2), 'RGBA')
        im.save(cache, optimize=True)
        im.save(webp_cache, 'WEBP', quality=82, method=4)
        meta.write_text(json.dumps(bounds))
        return cache, webp_cache, bounds


def webp_data_uri(path: Path) -> str:
    """Convert PNG or WebP image to compact WebP data URI for fast initial load."""
    webp_path = path.with_suffix('.webp')
    if not webp_path.exists() and path.exists():
        Image.open(path).save(webp_path, 'WEBP', quality=82, method=4)
    target = webp_path if webp_path.exists() else path
    mime = 'image/webp' if target.suffix == '.webp' else 'image/png'
    return f"data:{mime};base64," + base64.b64encode(target.read_bytes()).decode('ascii')


def kmz_bytes(proposal, selected):
    ns = 'http://www.opengis.net/kml/2.2'
    ET.register_namespace('', ns)

    def e(tag, parent, text=None):
        a = ET.SubElement(parent, '{' + ns + '}' + tag)
        if text is not None:
            a.text = str(text)
        return a

    root = ET.Element('{' + ns + '}kml')
    doc = e('Document', root)
    e('name', doc, 'La Cantina · propuesta preliminar ' + selected['id'])
    e('description', doc,
      f"Revisión 2 · {selected['stream_name']} · prioridad {selected['priority']}. "
      f"Tubería fuera del deslinde: {selected['outside_property_plan_m']:.1f} m en planta; "
      f"aducción exterior: {selected['adduction_outside_property_m']:.1f} m. No acredita acceso ni tenencia. "
      f"Cotas DTM, sin aforo; validar niveles y restitución en terreno. Quebradas: no permanentes, última prioridad y sin producción firme acreditada. "
      f"Altitudes clampToGround; no usar para replanteo de obra.")
    for _, r in proposal.iterrows():
        pm = e('Placemark', doc)
        e('name', pm, r['name'])
        e('description', pm, f"Alternativa {selected['id']} · {selected['stream_name']} · acceso exterior pendiente de validación")
        style = e('Style', pm)
        ls = e('LineStyle', style)
        e('color', ls, 'ff2788ff')
        e('width', ls, 4)
        if r.geometry.geom_type == 'Point':
            g = e('Point', pm)
            e('altitudeMode', g, 'clampToGround')
            e('coordinates', g, f'{r.geometry.x},{r.geometry.y},0')
        else:
            g = e('LineString', pm)
            e('tessellate', g, 1)
            e('altitudeMode', g, 'clampToGround')
            e('coordinates', g, ' '.join(f'{x},{y},0' for x, y in r.geometry.coords))
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
    return data.getvalue()


def main():
    r = json.loads((OUT / 'results.json').read_text(encoding='utf8'))
    sel = r['selected']
    geo = {
        name: json.loads((OUT / (name + '.geojson')).read_text(encoding='utf8'))
        for name in ['lotes', 'caminos', 'deslinde', 'hidrografia', 'curvas', 'alternativas', 'propuesta', 'cobertura', 'tramos_fuera_deslinde']
    }
    lots = gpd.read_file(OUT / 'lotes.geojson')
    bd = gpd.read_file(OUT / 'deslinde.geojson')
    c = lots.to_crs(32718).geometry.union_all().centroid
    cp = gpd.GeoSeries([c], crs=32718).to_crs(4326).iloc[0]
    m = folium.Map(location=[cp.y, cp.x], zoom_start=16, tiles=None, control_scale=True, prefer_canvas=True, zoom_control=False)

    layer_vars = {}
    t_sat = folium.TileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        name='Satélite · Esri World Imagery',
        attr='Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
        max_zoom=22, max_native_zoom=19
    ).add_to(m)
    layer_vars['tile_sat'] = t_sat.get_name()

    t_topo = folium.TileLayer(
        'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
        name='Relieve · OpenTopoMap',
        attr='Map data © OpenStreetMap contributors, SRTM | Map style © OpenTopoMap (CC-BY-SA)',
        max_zoom=22, max_native_zoom=17, show=False
    ).add_to(m)
    layer_vars['tile_topo'] = t_topo.get_name()

    # Ortofotos incorporadas en formato WebP optimizado (~88% menor peso, funcionan sin red).
    ortho_keys = ['ortho_10cm', 'ortho_full']
    for idx, (name, path, show, size) in enumerate([
        ('Ortomosaico 10 cm · vista web reducida', ROOT / 'LA_CANTINA_GSD10_EXTENT.tif', False, 1400),
        ('Ortomosaico completo · incluye sector norte', ROOT / 'LA_CANTINA_transparent_mosaic_group1.tif', True, 1700)
    ]):
        png, webp, bounds = png_overlay(path, size)
        ov = folium.raster_layers.ImageOverlay(
            webp_data_uri(png), bounds=bounds, name=name, opacity=.95, show=show, interactive=True,
            attr='Ortomosaico proporcionado por el propietario · remuestreado para web'
        ).add_to(m)
        layer_vars[ortho_keys[idx]] = ov.get_name()

    l_deslinde = folium.GeoJson(
        geo['deslinde'], name='Deslinde original · 104,57 ha',
        style_function=lambda f: dict(color='#f7f6ec', weight=3, fillOpacity=0, dashArray='8 5'),
        tooltip='Deslinde original (KML proporcionado)'
    ).add_to(m)
    layer_vars['deslinde'] = l_deslinde.get_name()

    l_cobertura = folium.GeoJson(
        geo['cobertura'], name='Cobertura DTM completa · sin recorte por deslinde', show=False,
        style_function=lambda f: dict(color='#e0af48', weight=2, fillColor='#e0af48', fillOpacity=.12),
        tooltip='Cobertura topográfica total; incluye sector norte fuera del deslinde'
    ).add_to(m)
    layer_vars['cobertura'] = l_cobertura.get_name()

    pal = ['#57bda9', '#f2c970', '#87b6d9', '#c9a6cf', '#f39975']
    for i, f in enumerate(geo['lotes']['features']):
        f['properties']['color'] = pal[i % len(pal)]
    l_lotes = folium.GeoJson(
        geo['lotes'], name='Lotes de subdivisión · 10',
        style_function=lambda f: dict(color=f['properties']['color'], weight=2, fillColor=f['properties']['color'], fillOpacity=.19),
        highlight_function=lambda f: dict(weight=4, fillOpacity=.35),
        tooltip=folium.GeoJsonTooltip(fields=['name'], aliases=['Lote'], sticky=False)
    ).add_to(m)
    layer_vars['lotes'] = l_lotes.get_name()

    labels = folium.FeatureGroup(name='Etiquetas de lotes', show=True).add_to(m)
    for _, lot in lots.iterrows():
        p = lot.geometry.representative_point()
        folium.Marker([p.y, p.x], icon=folium.DivIcon(html=f'<span class="lot-label">{html.escape(lot["name"])}</span>')).add_to(labels)
    layer_vars['lot_labels'] = labels.get_name()

    inventory = {s['stream_id']: s for s in r['stream_inventory']}
    for f in geo['hidrografia']['features']:
        props = f['properties']
        inv = inventory[props['id']]
        props.update(
            nombre=inv['stream_name'],
            cobertura=f"{inv['dtm_coverage_pct']:.1f}% del cauce con DTM",
            prioridad=inv['priority'],
            regimen='Permanente, según propietario' if props['tipo'] == 'arroyo' else 'No permanente; requeriría perforación según propietario. Última prioridad.'
        )
    for tipo, name, show, lkey in [
        ('arroyo', 'Prioridad 1 · arroyos permanentes completos', True, 'arroyos'),
        ('quebrada', 'Última prioridad · quebradas no permanentes', False, 'quebradas')
    ]:
        data = dict(type='FeatureCollection', features=[f for f in geo['hidrografia']['features'] if f['properties']['tipo'] == tipo])
        l_hydro = folium.GeoJson(
            data, name=name, show=show,
            style_function=lambda f: dict(
                color='#f3ca69' if f['properties']['id'] == 2 else '#37c4ef' if f['properties']['tipo'] == 'arroyo' else '#aeb8bc',
                weight=4 if f['properties']['id'] == 2 else 2.5,
                dashArray=None if f['properties']['tipo'] == 'arroyo' else '6 5'
            ),
            tooltip=folium.GeoJsonTooltip(fields=['nombre', 'id', 'regimen', 'cobertura'], aliases=['Cauce', 'ID', 'Régimen declarado', 'Topografía'])
        ).add_to(m)
        layer_vars[lkey] = l_hydro.get_name()

    north = gpd.read_file(OUT / 'hidrografia.geojson')
    np_ = north[north.id == 2].geometry.iloc[0].interpolate(.6, normalized=True)
    folium.Marker([np_.y, np_.x], icon=folium.DivIcon(html='<span class="north-label">Arroyo norte · ID 2</span>')).add_to(m)

    zs = [f['properties']['Elevation'] for f in geo['curvas']['features']]
    cmap = LinearColormap(['#3fa4bf', '#65c18c', '#ebdc73', '#d28a50', '#a25b67'], vmin=min(zs), vmax=max(zs))
    l_curvas = folium.GeoJson(
        geo['curvas'], name='Curvas completas · intervalo 1 m · sin recorte', show=False,
        style_function=lambda f: dict(
            color=cmap(f['properties']['Elevation']),
            weight=1.3 if f['properties']['Elevation'] % 5 == 0 else .65,
            opacity=.85
        ),
        tooltip=folium.GeoJsonTooltip(fields=['Elevation'], aliases=['Cota DTM (m)'])
    ).add_to(m)
    layer_vars['curvas'] = l_curvas.get_name()

    groups = {}
    downloads = {}
    for cand in r['alternatives']:
        cid = cand['id']
        active = False
        color = '#ff9c4b' if cand['tipo'] == 'arroyo' else '#d09ce5'
        group = folium.FeatureGroup(
            name=f"P{cand['priority']} · {cid} · {cand['stream_name']} · H {cand['hb']:.1f} m" + (' · revisar perfil' if not cand['hgl_ok'] else ''),
            show=active
        ).add_to(m)
        groups[cid] = group.get_name()
        feat = next(f for f in geo['alternativas']['features'] if f['properties']['candidate'] == cid)
        folium.GeoJson(feat, style_function=lambda f, col=color: dict(color=col, weight=5, opacity=.95), tooltip=f"{cid} · Tubería {cand['length_m']:.1f} m · trazado conceptual").add_to(group)
        folium.GeoJson(cand['adduction_geojson'], style_function=lambda f: dict(color='#f2db86', weight=4, dashArray='5 4'), tooltip=f"Aducción conceptual · {cand['adduction_length_m']:.1f} m").add_to(group)
        exterior = dict(type='FeatureCollection', features=[f for f in geo['tramos_fuera_deslinde']['features'] if f['properties']['candidate'] == cid])
        if exterior['features']:
            folium.GeoJson(exterior, style_function=lambda f: dict(color='#ed6565', weight=4, dashArray='7 5'), tooltip=f"{cid} · Fuera del deslinde: acceso y tenencia pendientes de validación").add_to(group)
        for key, title, zkey, letter in [('intake', 'Bocatoma', 'intake_z', 'B'), ('chamber', 'Cámara de carga', 'chamber_z', 'C'), ('tail', 'Turbina / restitución', 'tail_z', 'T')]:
            lon, lat = cand['points_wgs84'][key]
            where = 'Dentro del deslinde original' if cand['point_in_property'][key] else 'FUERA DEL DESLINDE · acceso y tenencia por verificar'
            popup = f"<b>{title} · {cid}</b><br>{cand['stream_name']} · prioridad {cand['priority']}<br><b>{where}</b><br>Cota del terreno: {cand[zkey]:.2f} m<br>Lat: {lat:.7f} · Lon: {lon:.7f}<br><small>Ubicación conceptual. Nivel de agua, inundación y emplazamiento de obra pendientes de terreno.</small>"
            folium.Marker([lat, lon], tooltip=title, icon=folium.DivIcon(html=f'<span class="site-pin" style="border-color:{color}">{letter}</span>'), popup=folium.Popup(popup, max_width=280)).add_to(group)
        from shapely.geometry import shape, Point
        features = [dict(name=title, geometry=Point(cand['points_wgs84'][key])) for key, title in [('intake', 'Bocatoma'), ('chamber', 'Cámara de carga'), ('tail', 'Turbina / restitución')]]
        features += [dict(name='Aducción', geometry=shape(cand['adduction_geojson']['features'][0]['geometry'])), dict(name='Tubería de presión', geometry=shape(feat['geometry']))]
        proposal = gpd.GeoDataFrame(features, crs=4326)
        kmz_c = kmz_bytes(proposal, cand)
        (OUT / f'la_cantina_{cid}.kmz').write_bytes(kmz_c)
        import csv
        buf = io.StringIO(newline='')
        wr = csv.DictWriter(buf, fieldnames=list(cand['scenarios'][0]))
        wr.writeheader()
        wr.writerows(cand['scenarios'])
        downloads[cid] = dict(kmz=base64.b64encode(kmz_c).decode(), csv=base64.b64encode(buf.getvalue().encode('utf-8-sig')).decode())

    from planning_map import add_planning
    planning = add_planning(m)

    # Embed compact WebP data URIs for terrain and solar overlays so they work even via file:// without network
    surface_overlays = {}
    for surf in ['hillshade', 'hypsometric', 'slope', 'aspect']:
        p = OUT / f'terrain_{surf}_web.png'
        if p.exists():
            surface_overlays[surf] = dict(
                uri=webp_data_uri(p),
                bounds=json.loads(p.with_suffix('.json').read_text(encoding='utf8'))
            )
    for season in ['summer', 'equinox', 'winter']:
        p = OUT / f'solar_hours_{season}_web.png'
        if p.exists():
            surface_overlays[f'solar_{season}'] = dict(
                uri=webp_data_uri(p),
                bounds=json.loads(p.with_suffix('.json').read_text(encoding='utf8'))
            )

    folium.LayerControl(position='topright', collapsed=True).add_to(m)
    Fullscreen(position='topright', title='Pantalla completa').add_to(m)
    MeasureControl(position='topright', primary_length_unit='meters', secondary_length_unit='kilometers', primary_area_unit='hectares').add_to(m)
    MousePosition(position='bottomright', separator=' · ', prefix='WGS84', num_digits=6).add_to(m)

    kmz = kmz_bytes(gpd.read_file(OUT / 'propuesta.geojson'), sel)
    (OUT / 'la_cantina_propuesta.kmz').write_bytes(kmz)

    payload = dict(
        results=r,
        groups=groups,
        layer_vars=layer_vars,
        surface_overlays=surface_overlays,
        downloads=downloads,
        map_name=m.get_name(),
        kmz=base64.b64encode(kmz).decode(),
        csv=base64.b64encode((OUT / 'escenarios.csv').read_bytes()).decode(),
        geojson=base64.b64encode((OUT / 'propuesta.geojson').read_bytes()).decode()
    )
    payload.update(planning)
    bounds = bd.total_bounds
    points = [p for s in planning['small']['sites'] for p in (s['intake_wgs84'], s['turbine_wgs84'])]
    payload['study_bounds'] = [
        [min(bounds[1], *(p[1] for p in points)), min(bounds[0], *(p[0] for p in points))],
        [max(bounds[3], *(p[1] for p in points)), max(bounds[2], *(p[0] for p in points))]
    ]
    styles = (ROOT / 'viewer_panel.html').read_text(encoding='utf8').split('<header')[0]
    panel = styles + (ROOT / 'planning_panel.html').read_text(encoding='utf8').replace('__PAYLOAD__', json.dumps(payload, ensure_ascii=False).replace('</', '<\\/'))
    m.get_root().html.add_child(folium.Element(panel.split('<!--SCRIPT-->')[0]))
    behavior = MacroElement()
    behavior._template = Template('{% macro script(this, kwargs) %}' + panel.split('<!--SCRIPT-->')[1] + '{% endmacro %}')
    m.add_child(behavior)
    m.get_root().header.add_child(folium.Element(
        '<title>La Cantina | Terreno, acceso, sol y microhidro</title>'
        '<meta name="description" content="Espacio de planificación territorial La Cantina: cotas y pendientes DTM, comparación de trazados de acceso a rotonda inferida, simulación solar en America/Coyhaique y estudio microhidro.">'
    ))
    rendered = m.get_root().render()
    cleaned = '\n'.join(line.rstrip() for line in rendered.splitlines()) + '\n'
    for target in (DIST / 'index.html', ROOT / 'index.html'):
        temp = target.with_suffix('.tmp')
        temp.write_text(cleaned, encoding='utf8')
        temp.replace(target)

    # Copy all referenced outputs & reports to DIST and DIST/outputs so relative links never 404
    out_files = [
        'la_cantina_propuesta.kmz', 'escenarios.csv', 'escenarios_todas_alternativas.csv',
        'results.json', 'inventario_cauces.json', 'propuesta.geojson', 'curvas.geojson',
        'curvas_completas.geojson', 'tramos_fuera_deslinde.geojson', 'perfil_tuberia.png',
        'microhidro_tres_sitios.json', 'microhidro_tres_sitios.geojson',
        'camino_propuesto.json', 'camino_propuesto.geojson', 'perfil_camino.csv',
        'presupuesto_productos.json', 'acceso_rotonda.kmz', 'rotonda.json',
        'terrain_contract.json', 'terrain_grid_2m.json', 'solar_presets.json',
        'caminos_candidatos.json', 'caminos_candidatos.geojson',
        'propuesta_acceso_microhidro.png', 'perfil_camino.png',
    ] + [f"la_cantina_{c['id']}.kmz" for c in r['alternatives']] + [f'microhidro_S{i}.kmz' for i in (1, 2, 3)]

    for name in out_files:
        src_p = OUT / name
        if src_p.exists():
            shutil.copy2(src_p, DIST / name)
            shutil.copy2(src_p, DIST / 'outputs' / name)

    for p in OUT.glob('*_web.*'):
        shutil.copy2(p, DIST / p.name)
        shutil.copy2(p, DIST / 'outputs' / p.name)

    for p in OUT.glob('acceso_*.kmz'):
        shutil.copy2(p, DIST / p.name)
        shutil.copy2(p, DIST / 'outputs' / p.name)

    for md_name in ['PROPUESTA_ACCESO_MICROHIDRO.md', 'INFORME_PREFACTIBILIDAD.md', 'APENDICE_POTENCIAL.md', 'README.md']:
        md_p = ROOT / md_name
        if md_p.exists():
            shutil.copy2(md_p, DIST / md_name)

    print('Visor generado:', DIST / 'index.html', 'MB:', round((DIST / 'index.html').stat().st_size / 1e6, 2))


if __name__ == '__main__':
    main()
