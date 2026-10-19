"""Regresión: arroyo norte sin recorte, prioridades y balances independientes."""
import json, math, zipfile, re
from pathlib import Path
import xml.etree.ElementTree as ET
import geopandas as gpd

ROOT=Path(__file__).parent;OUT=ROOT/'outputs'
r=json.loads((OUT/'results.json').read_text(encoding='utf8'));c=r['selected']
p=gpd.read_file(OUT/'propuesta.geojson').to_crs(32718)
b=gpd.read_file(OUT/'deslinde.geojson').to_crs(32718).geometry.union_all()
route=p[p.name=='Tubería de presión'].geometry.iloc[0]
lots=gpd.read_file(OUT/'lotes.geojson').to_crs(32718)
assert c['stream_id']==2 and c['tipo']=='arroyo' and c['priority']==1
assert c['hgl_ok'] and c['requires_external_access']
assert abs(route.difference(b).length-c['outside_property_plan_m'])<.02
assert route.difference(b).length>300,'El arroyo norte no debe recortarse al predio'
assert route.intersection(lots.geometry.map(lambda g:g.buffer(-4)).union_all()).length<.1
assert abs(route.length-c['length_plan_m'])<.01
assert c['length_m']>=c['length_plan_m']
assert abs(c['hb']-(c['intake_z']-c['tail_z']))<1e-8

# Preserva toda la cobertura vectorial, también fuera del KML.
original_curves=gpd.read_file(ROOT/'LA_CANTINA_elev1m_res100cm_size20_DTM.shp').to_crs(32718)
web_curves=gpd.read_file(OUT/'curvas.geojson').to_crs(32718)
full_curves=gpd.read_file(OUT/'curvas_completas.geojson').to_crs(32718)
assert len(original_curves)==len(web_curves)==len(full_curves)==512
assert full_curves.geometry.difference(b).length.sum()>10000
assert abs(original_curves.length.sum()-full_curves.length.sum())<.1
original_streams=gpd.read_file(ROOT/'hidro.shp').to_crs(32718)
export_streams=gpd.read_file(OUT/'hidrografia.geojson').to_crs(32718)
assert len(original_streams)==len(export_streams)==6
assert abs(original_streams.length.sum()-export_streams.length.sum())<.01
inventory={s['stream_id']:s for s in r['stream_inventory']}
assert inventory[2]['dtm_valid_length_m']>600
assert inventory[6]['dtm_valid_length_m']==0
assert all(s['priority']==3 for s in r['stream_inventory'] if s['tipo']=='quebrada')
assert [a['priority'] for a in r['alternatives']]==sorted(a['priority'] for a in r['alternatives'])

for a in r['alternatives']:
    for s in a['scenarios']:
        q=s['q_ls']/1000;d=s['diameter_mm']/1000
        v=q/(math.pi*d*d/4)
        hf=10.67*a['length_m']*q**1.852/(145**1.852*d**4.8704)
        hm=3*v*v/(2*9.81)
        hn=a['chamber_z']-a['tail_z']-hf-hm
        assert abs(s['hf_m']-hf)<1e-8 and abs(s['net_head_m']-hn)<1e-8
        assert hf<=.1*a['hb'] and (hf+hm)<=.1*a['penstock_head'] and v<=3
        assert abs(s['power_kw']-9.81*q*hn*.65)<1e-8
        assert abs(s['annual_kwh']-s['power_kw']*8760*.8)<1e-7
        rp=a['route_profile'];end=rp[-1]['distance_m']
        clearance=min(a['chamber_z']-hf*p['distance_m']/end-(p['terrain_m']-1) for p in rp)
        assert abs(s['min_hgl_clearance_m']-clearance)<1e-8
        if a['hgl_ok']:assert clearance>=0
    with zipfile.ZipFile(OUT/f"la_cantina_{a['id']}.kmz") as kmz:
        ns={'k':'http://www.opengis.net/kml/2.2'};kml=ET.fromstring(kmz.read('doc.kml'))
        assert len(kml.findall('.//k:Point',ns))==3
        assert len(kml.findall('.//k:LineString',ns))==2
        assert a['id'] in kml.find('.//k:Document/k:name',ns).text
        assert 'deslinde' in kml.find('.//k:Document/k:description',ns).text

doc=(ROOT/'index.html').read_text(encoding='utf8')
assert '__PAYLOAD__' not in doc and 'OpenTopoMap' in doc
assert 'Arroyo norte' in doc and 'quebradas no permanentes' in doc
assert 'KMZ · alternativa actual' in doc
assert 'C1-2-1' not in doc,'No debe conservar el identificador sustituido'
scripts=re.findall(r'<script[^>]*>(.*?)</script>',doc,re.S)
(OUT/'viewer-scripts.js').write_text('\n'.join(scripts),encoding='utf8')
print('OK: arroyo norte, seis cauces completos, 512 curvas sin recorte, prioridades, longitudes exteriores, perfiles, hidráulica de todas las alternativas y KMZ por selección.')
