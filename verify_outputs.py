"""Comprobaciones independientes de los entregables, sin modificar insumos."""
import json, math, zipfile, io, base64, re
from pathlib import Path
import xml.etree.ElementTree as ET
import geopandas as gpd
from shapely.geometry import shape

ROOT=Path(__file__).parent;OUT=ROOT/'outputs'
r=json.loads((OUT/'results.json').read_text(encoding='utf8'));c=r['selected']
p=gpd.read_file(OUT/'propuesta.geojson').to_crs(32718)
b=gpd.read_file(OUT/'deslinde.geojson').to_crs(32718).geometry.union_all()
route=p[p.name=='Tubería de presión'].geometry.iloc[0]
assert route.difference(b.buffer(.01)).length<.1, 'Ruta fuera del deslinde'
lots=gpd.read_file(OUT/'lotes.geojson').to_crs(32718)
assert route.intersection(lots.geometry.map(lambda g:g.buffer(-4)).union_all()).length<.1
assert abs(route.length-c['length_plan_m'])<.01
assert c['length_m']>=c['length_plan_m']
assert abs(c['hb']-(c['intake_z']-c['tail_z']))<1e-8
for s in r['scenarios']:
    q=s['q_ls']/1000;d=s['diameter_mm']/1000
    v=q/(math.pi*d*d/4)
    hf=10.67*c['length_m']*q**1.852/(145**1.852*d**4.8704)
    hm=3*v*v/(2*9.81)
    hn=c['chamber_z']-c['tail_z']-hf-hm
    assert abs(s['hf_m']-hf)<1e-8
    assert abs(s['net_head_m']-hn)<1e-8
    assert hf<=.1*c['hb']
    assert (hf+hm)<=.1*c['penstock_head']
    assert abs(s['power_kw']-9.81*q*hn*.65)<1e-8
    assert abs(s['annual_kwh']-s['power_kw']*8760*.8)<1e-7
with zipfile.ZipFile(OUT/'la_cantina_propuesta.kmz') as kmz:
    kml=ET.fromstring(kmz.read('doc.kml'));ns={'k':'http://www.opengis.net/kml/2.2'}
    assert len(kml.findall('.//k:Point',ns))==3
    assert len(kml.findall('.//k:LineString',ns))==2
doc=(ROOT/'index.html').read_text(encoding='utf8')
assert '__PAYLOAD__' not in doc
assert '50,6%' in doc and 'OpenTopoMap' in doc
scripts=re.findall(r'<script[^>]*>(.*?)</script>',doc,re.S)
(OUT/'viewer-scripts.js').write_text('\n'.join(scripts),encoding='utf8')
print('OK: CRS, ruta dentro del predio, interiores de lotes, longitudes, balance de energía, pérdidas, potencias, energía anual y estructura KMZ.')
