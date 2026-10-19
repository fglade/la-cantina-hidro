"""Exploración de acceso sur, rotonda desde lotes y tramos permanentes."""
from pathlib import Path
import json
import numpy as np
import geopandas as gpd
import rasterio
from shapely import maximum_inscribed_circle
from shapely.geometry import Point
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from inspect_data import read_kml

ROOT=Path(__file__).parent;OUT=ROOT/'outputs'
lots=read_kml(ROOT/'20260408_parelas_caminas_kml.kml').to_crs(32718)
lots=lots[lots.name.str.fullmatch(r'\d+')].copy()
streams=gpd.read_file(ROOT/'hidro.shp').to_crs(32718)
boundary=read_kml(ROOT/'20231207_deslinde_original.kml').to_crs(32718)
u=lots.geometry.union_all();void=u.convex_hull.difference(u)
parts=list(void.geoms) if hasattr(void,'geoms') else [void]
centers=[]
for p in parts:
    if p.area<50:continue
    mic=maximum_inscribed_circle(p,tolerance=.1)
    pt=Point(mic.coords[0]);centers.append(dict(point=[pt.x,pt.y],radius=mic.length,area=p.area))
print('VACIOS',centers,flush=True)
with rasterio.open(ROOT/'LA_CANTINA_dtm.tif') as d:
    z=d.read(1,masked=True)
    fig,ax=plt.subplots(figsize=(12,12))
    ax.imshow(z,extent=(d.bounds.left,d.bounds.right,d.bounds.bottom,d.bounds.top),cmap='terrain')
    boundary.boundary.plot(ax=ax,color='black');lots.boundary.plot(ax=ax,color='white',linewidth=1)
    for _,lot in lots.iterrows():
        p=lot.geometry.representative_point();ax.text(p.x,p.y,lot['name'],color='black',fontsize=10)
    for _,s in streams.iterrows():
        coords=np.array(s.geometry.coords);ss=np.linspace(0,s.geometry.length,200)
        points=[s.geometry.interpolate(float(t)) for t in ss]
        vals=np.array([float(v[0]) if not np.ma.is_masked(v[0]) else np.nan for v in d.sample([(p.x,p.y) for p in points],masked=True)])
        print('CAUCE',s.id,s.tipo,'extremos',coords[0].tolist(),coords[-1].tolist(),'cotas',vals[0],vals[-1],flush=True)
        x,y=s.geometry.xy;ax.plot(x,y,lw=2,label=f'ID {s.id} {s.tipo}')
    for i,c in enumerate(centers):
        ax.scatter(*c['point'],marker='x',s=100);ax.text(c['point'][0],c['point'][1],f"v{i} r{c['radius']:.1f}")
    ax.legend();ax.set_aspect('equal');fig.savefig(OUT/'exploracion_acceso.png',dpi=150,bbox_inches='tight')
(OUT/'rotonda_candidatos.json').write_text(json.dumps(centers,indent=2))
