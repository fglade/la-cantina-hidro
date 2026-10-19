from pathlib import Path
import json
import numpy as np
import geopandas as gpd
from inspect_data import read_kml
from scipy.optimize import least_squares

ROOT=Path(__file__).parent
g=read_kml(ROOT/'20260408_parelas_caminas_kml.kml').to_crs(32718)
g=g[g.name.str.fullmatch(r'\d+')]
xy=np.concatenate([np.array(p.exterior.coords)[:,:2] for p in g.geometry])
approx=np.array([685940.,4896170.])
xy=xy[np.linalg.norm(xy-approx,axis=1)<65]
rng=np.random.default_rng(42);best=None
local=xy-approx
for _ in range(12000):
    a=local[rng.choice(len(local),3,replace=False)]
    A=2*(a[1:]-a[0]);b=(a[1:]**2).sum(1)-(a[0]**2).sum()
    if abs(np.linalg.det(A))<1e-6:continue
    center=np.linalg.solve(A,b);radius=np.linalg.norm(a[0]-center)
    if not 12<radius<35 or np.linalg.norm(center)>35:continue
    residual=np.abs(np.linalg.norm(local-center,axis=1)-radius);inliers=residual<.15
    score=int(inliers.sum())
    if best is None or score>best[0]:best=(score,center,radius,inliers)
score,center,radius,inliers=best
fit=least_squares(lambda p:np.linalg.norm(local[inliers]-p[:2],axis=1)-p[2],[*center,radius])
center=fit.x[:2]+approx
result=dict(center_utm=center.tolist(),radius_m=float(fit.x[2]),boundary_vertices_matched=score,source='Arcos de linderos de lotes; no utiliza geometría CAMINOS')
(ROOT/'outputs/rotonda.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(result)
