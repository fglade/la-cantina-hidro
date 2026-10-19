"""Comprobación independiente de geometría, rasante, balances y costos."""
from pathlib import Path
import json, math, zipfile
import numpy as np
import geopandas as gpd
import rasterio
from shapely.geometry import Point
from inspect_data import read_kml
import xml.etree.ElementTree as ET
ROOT=Path(__file__).parent;OUT=ROOT/'outputs'
small=json.loads((OUT/'microhidro_tres_sitios.json').read_text(encoding='utf8'))
road=json.loads((OUT/'camino_propuesto.json').read_text(encoding='utf8'))
budget=json.loads((OUT/'presupuesto_productos.json').read_text(encoding='utf8'))
sf=gpd.read_file(OUT/'microhidro_tres_sitios.geojson').to_crs(32718)
rf=gpd.read_file(OUT/'camino_propuesto.geojson').to_crs(32718)
boundary=read_kml(ROOT/'20231207_deslinde_original.kml').to_crs(32718).geometry.union_all()
streams=gpd.read_file(ROOT/'hidro.shp').to_crs(32718)
assert len(small['sites'])==3 and {s['stream_id'] for s in small['sites']}=={1,2}
assert small['selected']=='S1' and small['season_days']==60
for s in small['sites']:
    frame=sf[sf.site==s['id']];line=frame[frame.geometry.geom_type=='LineString'].geometry.iloc[0]
    assert len(frame)==3 and s['priority']==1
    assert abs(line.length-s['length_plan_m'])<.01
    assert abs(line.difference(boundary).length-s['outside_property_plan_m'])<.01
    channel=streams[streams.id==s['stream_id']].geometry.iloc[0]
    for pt in frame[frame.geometry.geom_type=='Point'].geometry:
        assert pt.distance(channel)<.02 and not boundary.covers(pt)
    assert abs(s['gross_head_m']-(s['intake_z']-s['turbine_z']))<1e-8
    for p in s['plans']:
        q=p['q_ls']/1000;d=p['pipe_id_mm']/1000;v=4*q/(math.pi*d*d)
        hf=10.67*s['length_m']*q**1.852/(145**1.852*d**4.8704);hm=3*v*v/(2*9.81)
        hn=s['gross_head_m']-hf-hm;power=9.81*q*hn*.65
        assert abs(hf-p['hf_m'])<1e-8 and abs(hm-p['hm_m'])<1e-8
        assert abs(hn-p['net_head_m'])<1e-8 and abs(power-p['target_kw'])<1e-7
        assert hf+hm<=.1*s['gross_head_m'] and v<=2.5
        assert abs(p['season_60d_usable_kwh']-power*24*.8*.9*60)<1e-6
        assert abs(p['pipe_id_mm']-p['pipe_od_mm']*(1-2/11))<1e-8
        clearance=min(s['intake_z']-hf*x['distance_m']/s['length_plan_m']-(x['terrain_m']-.5) for x in s['route_profile'])
        assert clearance>=0 and abs(clearance-p['min_hgl_clearance_m'])<1e-7
    b=budget['budgets'][s['id']]
    for bound in ('low','high'):
        assert abs(sum(x[bound+'_clp'] for x in b['items'])*1.25-b['total_'+bound+'_clp'])<.001
    assert b['cable_voltage_drop_pct']<=5
    with zipfile.ZipFile(OUT/f"microhidro_{s['id']}.kmz") as z:
        k=ET.fromstring(z.read('doc.kml'));ns={'k':'http://www.opengis.net/kml/2.2'}
        assert len(k.findall('.//k:Point',ns))==2 and len(k.findall('.//k:LineString',ns))==1
line=rf[rf.geometry.geom_type=='LineString'].geometry.iloc[0]
assert line.is_simple and line.difference(boundary).length<.02
assert abs(line.length-road['length_plan_m'])<.01
south=streams[streams.id==1].geometry.iloc[0];mouth=Point(min([south.coords[0],south.coords[-1]],key=lambda p:p[0]))
assert Point(line.coords[0]).distance(mouth)<.01
assert line.intersection(south).difference(mouth.buffer(.02)).is_empty,'No cruzar el arroyo sur fuera del origen'
center=Point(json.loads((OUT/'rotonda.json').read_text(encoding='utf8'))['center_utm'])
assert Point(line.coords[-1]).distance(center)<.01
ss=np.array([x['distance_m'] for x in road['profile']]);zz=np.array([x['terrain_m'] for x in road['profile']]);dd=np.array([x['design_m'] for x in road['profile']])
assert np.abs(np.diff(dd)/np.diff(ss)).max()<=.10000001
assert abs(dd[0]-road['start_elevation_m'])<1e-8 and abs(dd[-1]-road['end_elevation_m'])<1e-8
assert road['length_plan_m']>=abs(dd[-1]-dd[0])/.1
assert abs(np.max(np.abs(dd-zz))-road['max_vertical_adjustment_m'])<1e-8
with rasterio.open(ROOT/'LA_CANTINA_dtm.tif') as dem:
    pts=[line.interpolate(float(x)) for x in ss];native=np.array([v[0] for v in dem.sample([(p.x,p.y) for p in pts])])
    assert np.allclose(native,zz,atol=.01)
radii=[]
for a,b,c in zip(list(line.coords)[:-2],list(line.coords)[1:-1],list(line.coords)[2:]):
    a,b,c=map(np.array,(a,b,c));ab=b-a;bc=c-b;cross=abs(ab[0]*bc[1]-ab[1]*bc[0])
    if cross>1e-7:radii.append(np.linalg.norm(ab)*np.linalg.norm(bc)*np.linalg.norm(c-a)/(2*cross))
assert min(radii)>14.9
assert road['legacy_roads_used'] is False
assert json.loads((OUT/'results.json').read_text(encoding='utf8'))['metadata']['legacy_roads_used'] is False
doc=(ROOT/'index.html').read_text(encoding='utf8')
assert 'Camino vehicular según subdivisión' not in doc
assert 'Microhidro S1' in doc and 'Acceso nuevo a rotonda' in doc
assert 'Acceso automatizado directo bloqueado' in doc
print('OK: tres pares permanentes, balances, costos, KMZ, desembocadura, rotonda del loteo, DTM nativo, rasante <=10%, curvas R15 y CAMINOS excluidos.')
