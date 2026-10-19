"""Acceso nuevo desde desembocadura sur; ignora CAMINOS del KML."""
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
from shapely.geometry import Point,LineString
from inspect_data import read_kml

ROOT=Path(__file__).parent;OUT=ROOT/'outputs'
STEP=2.;RADIUS=15.

def round_corners(coords,radius=RADIUS):
    out=[np.array(coords[0])]
    for a,v,b in zip(coords[:-2],coords[1:-1],coords[2:]):
        a,v,b=map(np.array,(a,v,b));u=(v-a)/np.linalg.norm(v-a);w=(b-v)/np.linalg.norm(b-v)
        theta=math.acos(float(np.clip(np.dot(u,w),-1,1)));cross=u[0]*w[1]-u[1]*w[0]
        if theta<1e-5:out.append(v);continue
        tangent=radius*math.tan(theta/2)
        if tangent>.45*min(np.linalg.norm(v-a),np.linalg.norm(b-v)):raise ValueError('Segmento insuficiente para radio de curva')
        p=v-u*tangent;q=v+w*tangent;sign=1 if cross>0 else -1
        center=p+sign*radius*np.array([-u[1],u[0]])
        alpha=math.atan2(*(p-center)[::-1]);angles=alpha+sign*np.linspace(0,theta,max(5,int(theta*radius)+1))
        out.extend(center+radius*np.array([np.cos(t),np.sin(t)]) for t in angles)
    out.append(np.array(coords[-1]));return LineString(out)

def main():
    all_lots=read_kml(ROOT/'20260408_parelas_caminas_kml.kml').to_crs(32718)
    lots=all_lots[all_lots.name.str.fullmatch(r'\d+')].copy()
    boundary=read_kml(ROOT/'20231207_deslinde_original.kml').to_crs(32718).geometry.union_all()
    streams=gpd.read_file(ROOT/'hidro.shp').to_crs(32718)
    south=streams[streams.id==1].geometry.iloc[0]
    # El extremo occidental de ID1 es su desembocadura en el río principal.
    start=Point(min((south.coords[0],south.coords[-1]),key=lambda p:p[0]))
    rotonda=json.loads((OUT/'rotonda.json').read_text(encoding='utf8'));goal=Point(rotonda['center_utm'])
    with rasterio.open(ROOT/'LA_CANTINA_dtm.tif') as dem:
        def sample(points):
            return np.array([float(v[0]) if not np.ma.is_masked(v[0]) else np.nan for v in dem.sample([(p.x,p.y) for p in points],masked=True)])
        z0,z1=map(float,sample([start,goal]));print('Acceso/rotonda',z0,z1,'mínimo teórico a 10%',abs(z1-z0)/.1,flush=True)
        left=dem.bounds.left;top=dem.bounds.top;w=math.ceil((dem.bounds.right-left)/STEP);h=math.ceil((top-dem.bounds.bottom)/STEP);tr=from_origin(left,top,STEP,STEP)
        grid=np.full((h,w),np.nan,dtype='float32')
        reproject(dem.read(1),grid,src_transform=dem.transform,src_crs=dem.crs,src_nodata=dem.nodata,dst_transform=tr,dst_crs=dem.crs,dst_nodata=np.nan,resampling=Resampling.bilinear)
        valid=np.isfinite(grid)
        fill=grid.copy();inds=distance_transform_edt(~valid,return_distances=False,return_indices=True);fill[~valid]=grid[tuple(inds[:,~valid])]
        terrain=gaussian_filter(fill,2.)  # sólo para búsqueda; perfil final DTM nativo.
        inside=rasterize([(boundary,1)],out_shape=(h,w),transform=tr).astype(bool)
        allowed=valid&inside
        # Evita cruzar el arroyo permanente sur salvo la conexión del origen.
        water_buffer=south.buffer(4.).difference(start.buffer(8.))
        water_mask=rasterize([(water_buffer,1)],out_shape=(h,w),transform=tr).astype(bool)
        allowed &= ~water_mask
        # Se permite afectar linderos; se penaliza cruzar por centro de lotes.
        inner=rasterize([(p.buffer(-6),1) for p in lots.geometry],out_shape=(h,w),transform=tr).astype(bool)
        gy,gx=np.gradient(terrain,STEP);side=np.hypot(gx,gy)
        cellcost=1.+inner*4.+np.maximum(side-.20,0)*8
        def rc(p):return rasterio.transform.rowcol(tr,p.x,p.y)
        def point(r,c):return np.array(rasterio.transform.xy(tr,r,c))
        a,b=rc(start),rc(goal)
        allowed[a]=True;allowed[b]=True
        moves=[(0,8),(3,8),(6,6),(8,3),(8,0),(8,-3),(6,-6),(3,-8),(0,-8),(-3,-8),(-6,-6),(-8,-3),(-8,0),(-8,3),(-6,6),(-3,8)]
        end_target=np.array([*b]);cache={}
        def edge(r,c,d,limit):
            key=(r,c,d,limit)
            if key in cache:return cache[key]
            dr,dc=moves[d];rr=r+dr;cc=c+dc
            if not(0<=rr<h and 0<=cc<w):cache[key]=None;return None
            ts=np.linspace(0,1,9);rs=np.rint(r+ts*dr).astype(int);cs=np.rint(c+ts*dc).astype(int)
            if not allowed[rs,cs].all():cache[key]=None;return None
            distance=STEP*math.hypot(dr,dc);elev=terrain[rs,cs]
            local=np.abs(np.diff(elev))/(distance/8)
            grade=abs(float(elev[-1]-elev[0]))/distance
            if grade>limit or float(local.max())>limit+.025:cache[key]=None;return None
            cost=distance*(float(cellcost[rs,cs].mean())+3*(grade/limit)**2)
            cache[key]=(rr,cc,cost);return cache[key]
        def solve(limit):
            distances={};prev={};queue=[]
            for d in range(16):
                key=(*a,d);distances[key]=0;heapq.heappush(queue,(0.,0.,key))
            seen=0
            while queue:
                _,cost,key=heapq.heappop(queue)
                if cost>distances.get(key,float('inf'))+1e-8:continue
                r,c,last=key;seen+=1
                if math.hypot(r-b[0],c-b[1])*STEP<18:
                    pp=point(r,c);connector=LineString([pp,(goal.x,goal.y)])
                    dz=abs(float(terrain[r,c])-z1)
                    if connector.length>0 and dz/connector.length<limit+.01:
                        keys=[key]
                        while keys[-1] in prev:keys.append(prev[keys[-1]])
                        keys.reverse();coords=[(start.x,start.y)]+[point(k[0],k[1]) for k in keys]+[(goal.x,goal.y)]
                        # Elimina el primer centro de celda, evita curva submétrica.
                        coords=[coords[0]]+coords[2:-1]+[coords[-1]]
                        if len(coords)>3:return coords,seen
                for delta in (-2,-1,0,1,2):
                    d=(last+delta)%16;res=edge(r,c,d,limit)
                    if res is None:continue
                    rr,cc,stepcost=res;nextkey=(rr,cc,d);newcost=cost+stepcost+abs(delta)*8
                    if newcost+1e-8<distances.get(nextkey,float('inf')):
                        distances[nextkey]=newcost;prev[nextkey]=key
                        heuristic=max(math.hypot(rr-b[0],cc-b[1])*STEP,abs(float(terrain[rr,cc])-z1)/limit)
                        heapq.heappush(queue,(newcost+heuristic,newcost,nextkey))
                if seen>700000:break
            return None,seen
        def solve_graded(limit):
            """Busca rasante y corredor juntos; desviación de búsqueda ≤5,5 m.

            Evita confundir pendiente del terreno natural con rasante de obra.
            La verificación final usa DTM nativo y programación lineal.
            """
            origin_level=round(z0*2);distances={};prev={};queue=[];seen=0
            for d in range(16):
                key=(*a,d,origin_level);distances[key]=0;heapq.heappush(queue,(0.,0.,key))
            edgecache={}
            while queue:
                _,cost,key=heapq.heappop(queue)
                if cost>distances.get(key,float('inf'))+1e-8:continue
                r,c,last,kz=key;zz_design=kz*.5;seen+=1
                distance_goal=math.hypot(r-b[0],c-b[1])*STEP
                if distance_goal<22 and distance_goal>2 and abs(zz_design-z1)/distance_goal<=limit:
                    keys=[key]
                    while keys[-1] in prev:keys.append(prev[keys[-1]])
                    keys.reverse();coords=[(start.x,start.y)]+[point(k[0],k[1]) for k in keys[1:]]+[(goal.x,goal.y)]
                    return coords,seen
                for delta in (-2,-1,0,1,2):
                    d=(last+delta)%16;ek=(r,c,d)
                    if ek not in edgecache:
                        dr,dc=moves[d];rr=r+dr;cc=c+dc
                        if not(0<=rr<h and 0<=cc<w):edgecache[ek]=None
                        else:
                            ts=np.linspace(0,1,9);rs=np.rint(r+ts*dr).astype(int);cs=np.rint(c+ts*dc).astype(int)
                            edgecache[ek]=(rr,cc,STEP*math.hypot(dr,dc),terrain[rs,cs],float(cellcost[rs,cs].mean())) if allowed[rs,cs].all() else None
                    edge_data=edgecache[ek]
                    if edge_data is None:continue
                    rr,cc,length,ground,costmean=edge_data
                    low=max(zz_design-limit*length,float(ground[-1])-5.0);high=min(zz_design+limit*length,float(ground[-1])+5.0)
                    lo=math.ceil(low*2);hi=math.floor(high*2)
                    if lo>hi:continue
                    choices={lo,hi,max(lo,min(hi,round(float(ground[-1])*2))),max(lo,min(hi,kz))}
                    for nk in choices:
                        e=nk*.5;profile=np.linspace(zz_design,e,9);earthwork=np.abs(profile-ground)
                        if earthwork.max()>5.5:continue
                        newcost=cost+length*(costmean+float(earthwork.mean())*1.5)+abs(delta)*15
                        nextkey=(rr,cc,d,nk)
                        if newcost+1e-8<distances.get(nextkey,float('inf')):
                            distances[nextkey]=newcost;prev[nextkey]=key
                            heuristic=max(math.hypot(rr-b[0],cc-b[1])*STEP,abs(e-z1)/limit)
                            heapq.heappush(queue,(newcost+8*heuristic,newcost,nextkey))
                if seen%50000==0:print('Estados',seen,'distancia objetivo',round(distance_goal),'cota',zz_design,flush=True)
                if seen>400000:break
            return None,seen
        route=None
        for limit,graded in ((.10,True),):
            coords,seen=solve_graded(limit) if graded else solve(limit);print('Búsqueda camino con rasante',limit,seen,'conexión',coords is not None,flush=True)
            if coords is None:continue
            # Conexión final corta puede afectar radio: conserva segmento recto
            # de aproximación si no existe longitud para fillete.
            try:route=round_corners(coords)
            except ValueError:
                coords=[p for i,p in enumerate(coords) if i==0 or i==len(coords)-1 or (np.linalg.norm(np.array(p)-np.array(coords[-1]))>24 and np.linalg.norm(np.array(p)-np.array(coords[0]))>24)]
                route=round_corners(coords)
            if not route.is_simple:route=None;continue
            ss=np.linspace(0,route.length,math.ceil(route.length/2)+1);pts=[route.interpolate(float(s)) for s in ss];zz=sample(pts)
            if not np.isfinite(zz).all():route=None;continue
            n=len(ss);A=lil_matrix((4*n-2,2*n));rhs=np.zeros(4*n-2)
            for i in range(n):
                A[2*i,i]=1;A[2*i,n+i]=-1;rhs[2*i]=zz[i]
                A[2*i+1,i]=-1;A[2*i+1,n+i]=-1;rhs[2*i+1]=-zz[i]
            for i in range(n-1):
                row=2*n+2*i;A[row,i+1]=1;A[row,i]=-1;rhs[row]=.10*(ss[i+1]-ss[i]);A[row+1,i]=1;A[row+1,i+1]=-1;rhs[row+1]=rhs[row]
            bounds=[(float(z)-6.,float(z)+6.) for z in zz]+[(0,None)]*n
            bounds[0]=(z0,z0);bounds[n-1]=(z1,z1)
            lp=linprog(np.r_[np.zeros(n),np.ones(n)],A_ub=A.tocsr(),b_ub=rhs,bounds=bounds,method='highs')
            if not lp.success:print('Rasante no factible con ±6 m de movimiento',flush=True);route=None;continue
            design=lp.x[:n];break
        if route is None:raise RuntimeError('No se encontró acceso con criterios 2WD: requiere replantear restricciones, no presentar como transitable.')
        grades=np.diff(design)/np.diff(ss);earth=design-zz
        # Proxy de movimientos longitudinales, no cubicación topográfica real.
        cut=float(np.trapezoid(np.maximum(-earth,0),ss)*5.);fillv=float(np.trapezoid(np.maximum(earth,0),ss)*5.)
        intrusions=[dict(lote=lot['name'],axis_length_m=float(route.intersection(lot.geometry.buffer(-1)).length),corridor_area_m2=float(route.buffer(2.5).intersection(lot.geometry).area)) for _,lot in lots.iterrows() if route.buffer(2.5).intersects(lot.geometry)]
        crossings=[]
        for _,s in streams.iterrows():
            inter=route.intersection(s.geometry)
            if not inter.is_empty:crossings.append(dict(stream_id=int(s.id),tipo=s.tipo,geometry=inter))
        data=dict(origin='Desembocadura occidental del arroyo ID1, indicada por usuario; no se acredita conexión a camino público',
                  rotonda_source=rotonda['source'],legacy_roads_used=False,road_status='Corredor conceptual, sin proyecto constructivo ni garantía de transitabilidad',
                  length_plan_m=route.length,length_3d_m=float(np.hypot(np.diff(ss),np.diff(design)).sum()),
                  start_elevation_m=z0,end_elevation_m=z1,elevation_gain_m=z1-z0,minimum_length_at_10pct_m=abs(z1-z0)/.1,
                  max_design_grade_pct=float(np.max(np.abs(grades))*100),p95_design_grade_pct=float(np.percentile(np.abs(grades),95)*100),
                  horizontal_curve_radius_m=RADIUS,carriageway_m=3.5,platform_m=5.,granular_thickness_m=.20,
                  granular_volume_m3=route.length*3.5*.2+math.pi*rotonda['radius_m']**2*.2,
                  cut_proxy_m3=cut,fill_proxy_m3=fillv,max_vertical_adjustment_m=float(np.max(np.abs(earth))),
                  outside_property_axis_m=float(route.difference(boundary).length),lot_impacts=intrusions,
                  stream_crossings=[{k:v for k,v in c.items() if k!='geometry'} for c in crossings],
                  profile=[dict(distance_m=float(s),terrain_m=float(z),design_m=float(v)) for s,z,v in zip(ss,zz,design)])
        def to_wgs(g):return gpd.GeoSeries([g],crs=32718).to_crs(4326).iloc[0]
        data['start_wgs84']=list(to_wgs(start).coords)[0];data['rotonda_wgs84']=list(to_wgs(goal).coords)[0]
        (OUT/'camino_propuesto.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
        features=[dict(name='Acceso nuevo 2WD · conceptual',geometry=route),dict(name='Inicio: desembocadura sur',geometry=start),dict(name='Rotonda objetivo inferida del loteo',geometry=goal),dict(name='Plataforma conceptual 5 m',geometry=route.buffer(2.5)),dict(name='Rotonda conceptual',geometry=goal.buffer(rotonda['radius_m']))]
        gpd.GeoDataFrame(features,crs=32718).to_crs(4326).to_file(OUT/'camino_propuesto.geojson',driver='GeoJSON')
        with (OUT/'perfil_camino.csv').open('w',newline='',encoding='utf-8-sig') as f:
            wr=csv.DictWriter(f,fieldnames=list(data['profile'][0]));wr.writeheader();wr.writerows(data['profile'])
        print(json.dumps({k:v for k,v in data.items() if k not in ('profile','lot_impacts')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
