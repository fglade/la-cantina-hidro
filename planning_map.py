"""Capas y exportaciones de la propuesta pequeña, comparación de accesos, terreno y energía solar."""
from pathlib import Path
import json, base64, io, zipfile
import xml.etree.ElementTree as ET
import geopandas as gpd
import folium

ROOT = Path(__file__).parent
OUT = ROOT / 'outputs'


def generic_kmz(frame, title, description):
    ns = 'http://www.opengis.net/kml/2.2'
    ET.register_namespace('', ns)
    root = ET.Element('{' + ns + '}kml')
    doc = ET.SubElement(root, '{' + ns + '}Document')

    def add(parent, tag, text=None):
        node = ET.SubElement(parent, '{' + ns + '}' + tag)
        if text is not None:
            node.text = str(text)
        return node

    add(doc, 'name', title)
    add(doc, 'description', description)
    for _, r in frame.iterrows():
        if r.geometry.geom_type not in ('Point', 'LineString', 'Polygon'):
            continue
        p = add(doc, 'Placemark')
        add(p, 'name', r.get('name', title))
        add(p, 'description', description)
        if r.geometry.geom_type == 'Polygon':
            g = add(p, 'LineString')
            add(g, 'tessellate', 1)
            add(g, 'altitudeMode', 'clampToGround')
            add(g, 'coordinates', ' '.join(f'{c[0]},{c[1]},0' for c in r.geometry.exterior.coords))
        else:
            g = add(p, r.geometry.geom_type)
            add(g, 'altitudeMode', 'clampToGround')
            if r.geometry.geom_type == 'LineString':
                add(g, 'tessellate', 1)
            add(g, 'coordinates', ' '.join(f'{c[0]},{c[1]},0' for c in r.geometry.coords))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml', ET.tostring(root, encoding='utf-8', xml_declaration=True))
    return buf.getvalue()


def add_planning(m):
    small = json.loads((OUT / 'microhidro_tres_sitios.json').read_text(encoding='utf8'))
    road = json.loads((OUT / 'camino_propuesto.json').read_text(encoding='utf8'))
    budget = json.loads((OUT / 'presupuesto_productos.json').read_text(encoding='utf8'))
    rotonda = json.loads((OUT / 'rotonda.json').read_text(encoding='utf8'))

    from terrain_contract import build_or_load_terrain_contract
    from solar_model import build_solar_presets

    terrain_contract = build_or_load_terrain_contract()
    terrain_grid_2m = json.loads((OUT / 'terrain_grid_2m.json').read_text(encoding='utf8'))
    solar_presets = build_solar_presets()

    cand_file = OUT / 'caminos_candidatos.json'
    if cand_file.exists():
        road_candidates = json.loads(cand_file.read_text(encoding='utf8'))
    else:
        road_candidates = dict(selected_id='baseline_10pct', rotonda=rotonda, candidates=[road])

    sf = gpd.read_file(OUT / 'microhidro_tres_sitios.geojson')
    rf = gpd.read_file(OUT / 'camino_propuesto.geojson')
    bd = gpd.read_file(OUT / 'deslinde.geojson').to_crs(32718).geometry.union_all()

    groups = {}
    downloads = {}
    colors = ['#f4a340', '#e3c265', '#a0e5e1']
    for s, col in zip(small['sites'], colors):
        sid = s['id']
        frame = sf[sf.site == sid]
        group = folium.FeatureGroup(name=f"Microhidro {sid} · {s['stream_name']} · 0,5–1 kW", show=sid == 'S1').add_to(m)
        groups[sid] = group.get_name()
        pipe = frame[frame.geometry.geom_type == 'LineString']
        folium.GeoJson(
            json.loads(pipe.to_json()),
            style_function=lambda f, c=col: dict(color=c, weight=6),
            tooltip=f"{sid} · Tubería 3D {s['length_m']:.1f} m · exterior {s['outside_property_plan_m']:.1f} m en planta"
        ).add_to(group)
        ext = pipe.to_crs(32718).geometry.iloc[0].difference(bd)
        if not ext.is_empty:
            ext = gpd.GeoSeries([ext], crs=32718).to_crs(4326)
            folium.GeoJson(
                json.loads(ext.to_json()),
                style_function=lambda f: dict(color='#ed6565', weight=3, dashArray='5 5'),
                tooltip='Fuera del deslinde: acceso y tenencia pendientes'
            ).add_to(group)
        for key, title, letter, zkey in [
            ('intake_wgs84', 'Bocatoma compacta', 'B', 'intake_z'),
            ('turbine_wgs84', 'Turbina / restitución', 'T', 'turbine_z')
        ]:
            lon, lat = s[key]
            popup = (
                f"<b>{sid} · {title}</b><br>{s['stream_name']}<br>"
                f"Cota terreno DTM: {s[zkey]:.2f} m<br>Lat {lat:.7f} · Lon {lon:.7f}<br>"
                f"<b>Ubicación exterior al deslinde; validar tenencia y acceso.</b><br>"
                f"Referencia sobre el cauce, no emplazamiento constructivo. Sala en margen segura frente a crecidas."
            )
            folium.Marker(
                [lat, lon],
                tooltip=f'{sid} · {title}',
                icon=folium.DivIcon(html=f'<span class="site-pin" style="border-color:{col}">{letter}</span>'),
                popup=folium.Popup(popup, max_width=285)
            ).add_to(group)
        kmz = generic_kmz(
            frame,
            'La Cantina · microhidro ' + sid,
            'Propuesta conceptual 0,5–1 kW. Sin aforo ni acceso exterior acreditado. Cotas de terreno DTM, no niveles de agua medidos. No usar para replanteo. CAMINOS hipotéticos excluidos.'
        )
        (OUT / f'microhidro_{sid}.kmz').write_bytes(kmz)
        downloads[sid] = base64.b64encode(kmz).decode()

    rg = folium.FeatureGroup(name=f"Acceso nuevo a rotonda · conceptual · {road['length_plan_m']:.0f} m", show=True).add_to(m)
    line = rf[rf.geometry.geom_type == 'LineString']
    folium.GeoJson(json.loads(line.to_json()), style_function=lambda f: dict(color='#153f3d', weight=9, opacity=.8)).add_to(rg)
    folium.GeoJson(
        json.loads(line.to_json()),
        style_function=lambda f: dict(color='#faf4c4', weight=4),
        tooltip='Nuevo corredor: rasante calculada ≤10%; no acredita transitabilidad actual'
    ).add_to(rg)
    areas = rf[rf.geometry.geom_type == 'Polygon']
    folium.GeoJson(
        json.loads(areas.to_json()),
        style_function=lambda f: dict(color='#faf4c4', weight=1, fillColor='#faf4c4', fillOpacity=.14),
        tooltip=folium.GeoJsonTooltip(fields=['name'], aliases=['Huella conceptual'])
    ).add_to(rg)
    for key, title in [
        ('start_wgs84', 'Inicio actual: desembocadura ID1'),
        ('rotonda_wgs84', 'Rotonda inferida (arcos de linderos)')
    ]:
        lon, lat = road[key]
        folium.Marker(
            [lat, lon],
            tooltip=title,
            popup=title + '<br>No acredita acceso público ni obra existente.',
            icon=folium.Icon(color='darkgreen', icon='road', prefix='fa')
        ).add_to(rg)

    roadkmz = generic_kmz(
        rf,
        'La Cantina · nuevo acceso hasta rotonda',
        f"Corredor conceptual de {road['length_plan_m']:.1f} m en planta. Rasante de diseño ≤10%; cortes/rellenos hasta {road['max_vertical_adjustment_m']:.2f} m. Requiere proyecto vial, drenajes y movimiento de tierra. CAMINOS entregados no utilizados. No es camino existente ni certificado para autos."
    )
    (OUT / 'acceso_rotonda.kmz').write_bytes(roadkmz)

    # Also build KMZs for each precomputed road candidate so downloads match the selected candidate
    candidate_kmzs = {'baseline_10pct': base64.b64encode(roadkmz).decode()}
    from shapely.geometry import shape, Point as ShpPoint
    for cand in road_candidates.get('candidates', []):
        cid = cand['id']
        if cid in candidate_kmzs:
            continue
        geom_line = shape(cand['geometry_wgs84'])
        c_rows = [
            dict(name=cand['title'], geometry=geom_line),
            dict(name='Inicio: desembocadura ID1', geometry=ShpPoint(cand['start_wgs84'])),
            dict(name='Conexión en rotonda inferida', geometry=ShpPoint(cand.get('goal_wgs84', cand['rotonda_wgs84']))),
        ]
        c_gdf = gpd.GeoDataFrame(c_rows, crs=4326)
        c_kmz = generic_kmz(
            c_gdf,
            f"La Cantina · {cand['title']}",
            f"Trazado conceptual {cand['length_plan_m']:.1f} m en planta · pendiente máx. {cand['max_design_grade_pct']:.1f}% · R{cand['horizontal_curve_radius_m']:.0f} m. No es proyecto vial definitivo."
        )
        (OUT / f'acceso_{cid}.kmz').write_bytes(c_kmz)
        candidate_kmzs[cid] = base64.b64encode(c_kmz).decode()

    return dict(
        small=small,
        road=road,
        road_candidates=road_candidates,
        road_candidate_kmzs=candidate_kmzs,
        rotonda=rotonda,
        budget=budget,
        terrain_contract=terrain_contract,
        terrain_grid_2m=terrain_grid_2m,
        solar_presets=solar_presets,
        small_groups=groups,
        small_kmz=downloads,
        road_group=rg.get_name(),
        road_kmz=base64.b64encode(roadkmz).decode(),
    )
