"""Estudio reproducible La Cantina: EPSG:32718 para cálculo, 4326 para entrega."""
from pathlib import Path
import json, math, csv
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize, shapes
from rasterio.transform import from_origin
from rasterio.enums import Resampling
from shapely.geometry import LineString, Point, box
from shapely.ops import substring
from shapely import force_2d
from scipy.ndimage import distance_transform_edt, median_filter
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from inspect_data import read_kml
from hydraulics import scenario

ROOT=Path(__file__).parent
OUT=ROOT/'outputs'
OUT.mkdir(exist_ok=True)
CRS=32718

def lines(g):
    if g.is_empty: return []
    if g.geom_type=='LineString': return [force_2d(g)]
    return [x for part in g.geoms for x in lines(part)]

def main():
    lots_all=read_kml(ROOT/'20260408_parelas_caminas_kml.kml').to_crs(CRS)
    lots=lots_all[lots_all.name.str.fullmatch(r'\d+')].copy()
    # CAMINOS del KML son hipotéticos: no intervienen como acceso ni costo.
    roads=lots_all[~lots_all.index.isin(lots.index)].copy()
    boundary=read_kml(ROOT/'20231207_deslinde_original.kml').to_crs(CRS)
    for g in (lots, roads, boundary): g.geometry=g.geometry.make_valid()
    property_geom=boundary.geometry.union_all()
    streams=gpd.read_file(ROOT/'hidro.shp').to_crs(CRS)
    contours=gpd.read_file(ROOT/'LA_CANTINA_elev1m_res100cm_size20_DTM.shp')
    contours.geometry=contours.geometry.map(force_2d)
    with rasterio.open(ROOT/'LA_CANTINA_dtm.tif') as dem:
        z=dem.read(1,masked=True)
        def sample(points):
            vals=np.array([float(a[0]) if not np.ma.is_masked(a[0]) else np.nan for a in dem.sample([(p.x,p.y) for p in points],masked=True)])
            vals[(vals<=-9999)|(~np.isfinite(vals))]=np.nan
            return vals
        # Revisión 2: el deslinde es referencia de tenencia, no un recorte
        # hidrológico. Se analiza cada cauce completo donde existe DTM válido.
        candidates=[]; profiles=[]; stream_inventory=[]
        for _,row in streams.iterrows():
            valid_length=0.;run_count=0
            for partno,line in enumerate(lines(row.geometry)):
                distances=np.linspace(0,line.length,max(3,int(line.length/2)+1))
                pts=[line.interpolate(d) for d in distances]
                zs=sample(pts)
                valid=np.isfinite(zs)
                starts=np.where(valid & ~np.r_[False,valid[:-1]])[0]
                ends=np.where(valid & ~np.r_[valid[1:],False])[0]
                for run,(a,b) in enumerate(zip(starts,ends)):
                    valid_length+=float(distances[b]-distances[a]);run_count+=1
                    print('Tramo',int(row.id),partno,run,'a,b',int(a),int(b),'long',float(distances[b]-distances[a]),flush=True)
                    if b-a<10: continue
                    ds=distances[a:b+1]; zz=median_filter(zs[a:b+1],size=5,mode='nearest')
                    ll=substring(line,float(ds[0]),float(ds[-1]))
                    if zz[-1]>zz[0]:
                        ll=LineString(list(ll.coords)[::-1]); zz=zz[::-1]; ds=ll.length-(ds[::-1]-ds[0])
                    else: ds=ds-ds[0]
                    # Evita que redondeo negativo (~1e-14) se interprete como
                    # distancia desde el final en Shapely.interpolate.
                    ds=np.clip(ds,0,ll.length)
                    # Alto seguido por bajo en el mismo tramo continuo.
                    best=(-1,0,0)
                    top=0
                    for j in range(1,len(zz)):
                        if zz[j]>zz[top]: top=j
                        h=zz[top]-zz[j]
                        if h>best[0] and ds[j]-ds[top]>=30: best=(float(h),top,j)
                    h,i,j=best
                    print('Extremos',row.id,h,i,j,'ds',ds[i],ds[j],flush=True)
                    if h<3: continue
                    intake=ll.interpolate(float(ds[i])); tail=ll.interpolate(float(ds[j]))
                    chamber_s=min(float(ds[i]+12),float(ds[j]-10))
                    chamber=ll.interpolate(chamber_s)
                    # Busca cámara dentro de los primeros 30 m con cota menor.
                    cap_z=float(sample([intake])[0])
                    for ss in np.arange(ds[i]+6,min(ds[i]+32,ds[j]-10),2):
                        p=ll.interpolate(float(ss)); pz=sample([p])[0]
                        if np.isfinite(pz) and pz<cap_z-.3:
                            chamber=p; chamber_s=float(ss); break
                    cz,tz=map(float,sample([chamber,tail]))
                    print('Cotas',row.id,cap_z,cz,tz,flush=True)
                    if not np.isfinite([cap_z,cz,tz]).all() or cz-tz<3 or cap_z-tz<3: continue
                    cid=f"C{int(row.id)}-{partno+1}-{run+1}"
                    adduction=substring(ll,float(ds[i]),chamber_s)
                    candidates.append(dict(id=cid,stream_id=int(row.id),tipo=row.tipo,
                                           stream_name='Arroyo norte' if int(row.id)==2 else f'{str(row.tipo).capitalize()} {int(row.id)}',
                                           priority=1 if row.tipo=='arroyo' else 3,
                                           hydrology='Permanente según propietario' if row.tipo=='arroyo' else 'No permanente; acceso al agua requeriría perforación según propietario',
                                           intake=intake,chamber=chamber,tail=tail,
                                           intake_z=cap_z,chamber_z=cz,tail_z=tz,hb=cap_z-tz,penstock_head=cz-tz,
                                           adduction=adduction,watercourse=substring(ll,float(ds[i]),float(ds[j]))))
                    profiles.extend(dict(candidate=cid,distance_m=float(d),elevation_m=float(e)) for d,e in zip(ds,zz))
            stream_inventory.append(dict(stream_id=int(row.id),tipo=row.tipo,
                                         stream_name='Arroyo norte' if int(row.id)==2 else f'{str(row.tipo).capitalize()} {int(row.id)}',
                                         priority=1 if row.tipo=='arroyo' else 3,
                                         total_length_m=float(row.geometry.length),dtm_valid_length_m=valid_length,
                                         dtm_coverage_pct=100*valid_length/row.geometry.length,valid_runs=run_count,
                                         outside_property_m=float(row.geometry.difference(property_geom).length),
                                         status='Con cotas DTM; analizado sin recorte predial' if valid_length>=20 else 'Sin DTM suficiente; conservar visible y solicitar topografía'))
        print('Candidatos',[(c['id'],c['tipo'],c['hb'],c['intake_z'],c['chamber_z'],c['tail_z']) for c in candidates],flush=True)
        # Grilla a 2 m, distancias medidas en UTM; el DEM nativo se usa para cotas.
        step=2.
        w=math.ceil((dem.bounds.right-dem.bounds.left)/step); ht=math.ceil((dem.bounds.top-dem.bounds.bottom)/step)
        tr=from_origin(dem.bounds.left,dem.bounds.top,step,step)
        from rasterio.warp import reproject
        grid=np.full((ht,w),np.nan,dtype='float32')
        reproject(z.filled(np.nan),grid,src_transform=dem.transform,src_crs=dem.crs,
                  dst_transform=tr,dst_crs=dem.crs,src_nodata=np.nan,dst_nodata=np.nan,resampling=Resampling.bilinear)
        def burn(geoms): return rasterize([(g,1) for g in geoms if not g.is_empty],out_shape=grid.shape,transform=tr,fill=0).astype(bool)
        inside=burn([property_geom])
        # La ruta puede salir del deslinde: se cuantifica y señala, no se
        # presume dominio o autorización de uso sobre el tramo exterior.
        # Sólo linderos: el trazado CAMINOS se conserva como antecedente,
        # pero no participa en ninguna preferencia hidráulica.
        inner=burn([g.buffer(-4) for g in lots.geometry])
        boundarymask=burn([g.boundary.buffer(4) for g in lots.geometry]+[property_geom.boundary.buffer(4)])
        preferred=boundarymask
        base=np.where(preferred,1.3,np.where(inner,25.,4.))
        finite=np.isfinite(grid)
        inside_finite=inside & finite
        ids=np.arange(ht*w).reshape(ht,w)
        def rc(p):
            r,c=rasterio.transform.rowcol(tr,p.x,p.y)
            return max(0,min(ht-1,r)),max(0,min(w-1,c))
        def cellpoint(r,c):
            x,y=rasterio.transform.xy(tr,r,c); return (float(x),float(y))
        alternatives=[]
        for cand in candidates:
            # Ruta bajo el nivel de cámara; no se modela sifón ni bombeo.
            allowed=finite & (grid<=cand['chamber_z']+.3)
            def endpoint_cell(point):
                rr,cc=rc(point);opts=[]
                for row in range(max(0,rr-8),min(ht,rr+9)):
                    for col in range(max(0,cc-8),min(w,cc+9)):
                        if allowed[row,col]:
                            xy=cellpoint(row,col)
                            connector=LineString([(point.x,point.y),xy])
                            connector_pts=[connector.interpolate(float(t),normalized=True) for t in np.linspace(0,1,max(3,int(connector.length/.5)+1))]
                            if np.isfinite(sample(connector_pts)).all():opts.append((connector.length,row,col))
                if not opts:return None
                _,row,col=min(opts);return row,col
            a,b=endpoint_cell(cand['chamber']),endpoint_cell(cand['tail'])
            if a is None or b is None:continue
            costs=base.copy()
            # Penaliza proximidad al techo hidráulico y pendientes abruptas.
            gy,gx=np.gradient(np.nan_to_num(grid,nan=0.),step)
            costs*=1+np.minimum(np.hypot(gx,gy),3)*.7
            rs=[];cs=[];vs=[]
            for dr,dc in [(0,1),(1,0),(1,1),(1,-1)]:
                r0=max(0,-dr);r1=min(ht,ht-dr);c0=max(0,-dc);c1=min(w,w-dc)
                sa=(slice(r0,r1),slice(c0,c1));sb=(slice(r0+dr,r1+dr),slice(c0+dc,c1+dc))
                ok=allowed[sa]&allowed[sb]
                if dr and dc:
                    ok &= allowed[slice(r0+dr,r1+dr),slice(c0,c1)] & allowed[slice(r0,r1),slice(c0+dc,c1+dc)]
                ii=ids[sa][ok];jj=ids[sb][ok]
                vv=(costs[sa][ok]+costs[sb][ok])/2*step*math.hypot(dr,dc)
                rs.extend([ii,jj]);cs.extend([jj,ii]);vs.extend([vv,vv])
            graph=coo_matrix((np.concatenate(vs),(np.concatenate(rs),np.concatenate(cs))),shape=(ht*w,ht*w)).tocsr()
            dist,pred=dijkstra(graph,directed=False,indices=int(ids[a]),return_predecessors=True)
            end=int(ids[b]); start=int(ids[a])
            if not np.isfinite(dist[end]):
                cand['route_status']='sin conexión bajo nivel de cámara';print(cand['id'],cand['route_status'],a,b,grid[a],grid[b],finite[a],finite[b],flush=True);continue
            path=[end]
            while path[-1]!=start:
                prev=int(pred[path[-1]])
                if prev<0: raise RuntimeError('Predecesor inválido')
                path.append(prev)
            path.reverse()
            coords=[(cand['chamber'].x,cand['chamber'].y)]+[cellpoint(*divmod(n,w)) for n in path]+[(cand['tail'].x,cand['tail'].y)]
            route=LineString(coords).simplify(.35,preserve_topology=True)
            # Longitud 3D a intervalos de 2 m; se conserva también planta.
            ss=np.linspace(0,route.length,max(3,math.ceil(route.length/2)+1))
            pp=[route.interpolate(float(t)) for t in ss];zz=sample(pp)
            if not np.isfinite(zz).all(): continue
            length3d=float(np.hypot(np.diff(ss),np.diff(zz)).sum())
            intrusions=[]
            innergeom=lots.geometry.map(lambda x:x.buffer(-4)).union_all()
            cross=route.intersection(innergeom)
            for _,lot in lots.iterrows():
                length=route.intersection(lot.geometry.buffer(-4)).length
                if length>0.5: intrusions.append(dict(lote=lot['name'],length_m=length))
            pref_length=route.intersection(lots.geometry.map(lambda x:x.boundary.buffer(4)).union_all().union(property_geom.boundary.buffer(4))).length
            cand.update(route=route,length_m=length3d,length_plan_m=route.length,
                        interior_crossing_m=cross.length,intrusions=intrusions,preferred_pct=100*pref_length/route.length,
                        score=cand['penstock_head']/length3d,
                        route_profile=[dict(distance_m=float(s),terrain_m=float(v)) for s,v in zip(ss,zz)],
                        route_status='calculada')
            outside=route.difference(property_geom)
            adduction_outside=cand['adduction'].difference(property_geom)
            cand.update(outside_property_plan_m=float(outside.length),
                        adduction_outside_property_m=float(adduction_outside.length),
                        outside_property_pct=100*outside.length/route.length,
                        requires_external_access=bool(outside.length>.1 or adduction_outside.length>.1),
                        max_static_pressure_bar=float(max(0,cand['chamber_z']-float((zz-1).min()))*.0980665),
                        point_in_property={key:bool(property_geom.buffer(.001).covers(cand[key])) for key in ('intake','chamber','tail')})
            # Control piezométrico preliminar, enterramiento supuesto 1 m.
            print('Ruta',cand['id'],'Hb',cand['hb'],'Hcam',cand['penstock_head'],'L',length3d,flush=True)
            scs=[scenario(q,cand['hb'],cand['penstock_head'],length3d,cand['route_profile'],cand['chamber_z']) for q in (10,25,50,100)]
            cand['min_hgl_clearance_m']=min(s['min_hgl_clearance_m'] for s in scs)
            cand['hgl_ok']=all(s['profile_ok'] for s in scs)
            alternatives.append(cand)
        valid=[c for c in alternatives if c['tipo']=='arroyo' and c['hgl_ok']]
        if not valid: raise RuntimeError('No se encontró alternativa permanente con ruta viable.')
        # Prioridad: permanencia, no atravesar interior de lotes, mayor salto.
        low_cross=[c for c in valid if c['interior_crossing_m']<=10]
        pool=low_cross or valid
        selected=max(pool,key=lambda c:c['hb'])
        selected['selection_rule']='Arroyos permanentes primero, incluido arroyo norte sin recorte por deslinde; perfil aceptable, mínimo cruce interior y mayor salto. Quebradas excluidas de la selección principal.'
        alternatives.sort(key=lambda c:(c['priority'],0 if c['stream_id']==2 else 1,-c['hb']))
        scenarios=[scenario(q,selected['hb'],selected['penstock_head'],selected['length_m'],selected['route_profile'],selected['chamber_z']) for q in (10,25,50,100)]
        print('ALTERNATIVAS',[(c['id'],c['tipo'],round(c['hb'],2),round(c['length_m'],1),round(c['interior_crossing_m'],1),c['hgl_ok']) for c in alternatives],flush=True)
        print('SELECCION',selected['id'],'ESCENARIOS',scenarios,flush=True)
        # Exporta datos WGS84 sin modificar los originales.
        for name,g in [('lotes',lots),('caminos',roads),('deslinde',boundary),('hidrografia',streams)]:
            g.to_crs(4326).to_file(OUT/(name+'.geojson'),driver='GeoJSON')
        web_contours=contours.copy();web_contours.geometry=web_contours.geometry.simplify(.75)
        web_contours[['Elevation','geometry']].to_crs(4326).to_file(OUT/'curvas.geojson',driver='GeoJSON')
        # Conserva también una exportación sin simplificar para auditoría SIG.
        contours[['Elevation','geometry']].to_crs(4326).to_file(OUT/'curvas_completas.geojson',driver='GeoJSON')
        route_rows=[]
        for c in alternatives:
            route_rows.append(dict(candidate=c['id'],tipo=c['tipo'],stream_name=c['stream_name'],priority=c['priority'],selected=c['id']==selected['id'],hb_m=c['hb'],length_m=c['length_m'],outside_m=c['outside_property_plan_m'],geometry=c['route']))
        gpd.GeoDataFrame(route_rows,crs=CRS).to_crs(4326).to_file(OUT/'alternativas.geojson',driver='GeoJSON')
        features=[]
        for name,key in [('Bocatoma','intake'),('Cámara de carga','chamber'),('Turbina / restitución','tail'),('Aducción','adduction'),('Tubería de presión','route')]:
            features.append(dict(name=name,candidate=selected['id'],stream_id=selected['stream_id'],external_access=selected['requires_external_access'],geometry=selected[key]))
        gpd.GeoDataFrame(features,crs=CRS).to_crs(4326).to_file(OUT/'propuesta.geojson',driver='GeoJSON')
        def clean(c):
            obj={k:v for k,v in c.items() if k not in ('intake','chamber','tail','adduction','watercourse','route','route_profile')}
            obj['points_wgs84']={k:list(gpd.GeoSeries([c[k]],crs=CRS).to_crs(4326).iloc[0].coords)[0] for k in ('intake','chamber','tail')}
            obj['route_profile']=c['route_profile']
            obj['scenarios']=[scenario(q,c['hb'],c['penstock_head'],c['length_m'],c['route_profile'],c['chamber_z']) for q in (10,25,50,100)]
            obj['adduction_length_m']=c['adduction'].length
            obj['adduction_geojson']=json.loads(gpd.GeoSeries([c['adduction']],crs=CRS).to_crs(4326).to_json())
            return obj
        # Cobertura real en el predio, vectorizada a resolución de análisis.
        cell_area=step**2
        metadata=dict(revision=3,legacy_roads_used=False,analysis_scope='Cauces completos; CAMINOS hipotéticos excluidos de costos y trazados',
                      northern_stream_id=2,crs_metric=CRS,dem_resolution_m=dem.res[0],grid_step_m=step,property_area_ha=property_geom.area/10000,
                      dem_coverage_pct=100*(inside_finite.sum()*cell_area)/property_geom.area,
                      dtm_full_area_ha=finite.sum()*cell_area/10000,contour_feature_count=len(contours),
                      lots_area_ha=lots.geometry.area.sum()/10000,lot_count=len(lots),
                      dem_valid_range_m=[float(z.min()),float(z.max())],
                      warning='Se incluye el arroyo norte fuera del deslinde donde hay DTM. Las obras exteriores requieren validar acceso y tenencia; no se extrapolan cotas donde falta DTM. Quebradas no permanentes: última prioridad, sin producción firme acreditada.')
        from shapely.geometry import shape
        from shapely.ops import unary_union
        footprint=unary_union([shape(g) for g,v in shapes(finite.astype('uint8'),mask=finite,transform=tr) if v==1]).simplify(2)
        gpd.GeoDataFrame([dict(name='Cobertura DTM válida completa, sin recorte predial',geometry=footprint)],crs=CRS).to_crs(4326).to_file(OUT/'cobertura.geojson',driver='GeoJSON')
        exterior_rows=[dict(candidate=c['id'],geometry=part) for c in alternatives for key in ('route','adduction') for part in lines(c[key].difference(property_geom))]
        gpd.GeoDataFrame(exterior_rows,crs=CRS).to_crs(4326).to_file(OUT/'tramos_fuera_deslinde.geojson',driver='GeoJSON')
        result=dict(metadata=metadata,stream_inventory=stream_inventory,selected=clean(selected),alternatives=[clean(c) for c in alternatives],scenarios=scenarios,route_profile=selected['route_profile'])
        (OUT/'inventario_cauces.json').write_text(json.dumps(stream_inventory,ensure_ascii=False,indent=2),encoding='utf8')
        (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        with (OUT/'escenarios.csv').open('w',newline='',encoding='utf-8-sig') as f:
            wr=csv.DictWriter(f,fieldnames=list(scenarios[0]));wr.writeheader();wr.writerows(scenarios)
        with (OUT/'perfil_cauce.csv').open('w',newline='',encoding='utf-8-sig') as f:
            wr=csv.DictWriter(f,fieldnames=['candidate','distance_m','elevation_m']);wr.writeheader();wr.writerows(profiles)
        all_scenarios=[dict(candidate=c['id'],stream_name=c['stream_name'],priority=c['priority'],**s) for c in alternatives for s in clean(c)['scenarios']]
        with (OUT/'escenarios_todas_alternativas.csv').open('w',newline='',encoding='utf-8-sig') as f:
            wr=csv.DictWriter(f,fieldnames=list(all_scenarios[0]));wr.writeheader();wr.writerows(all_scenarios)
        # Resumen cartográfico para QA independiente de Folium.
        fig,ax=plt.subplots(figsize=(11,12))
        ax.imshow(np.where(finite,grid,np.nan),extent=(tr.c,tr.c+w*step,tr.f-ht*step,tr.f),cmap='terrain',alpha=.8)
        boundary.boundary.plot(ax=ax,color='black');lots.boundary.plot(ax=ax,color='white',linewidth=.8)
        streams.plot(ax=ax,color='#1389bd',linewidth=1.5)
        for c in alternatives:
            xs,ys=c['route'].xy;ax.plot(xs,ys,label=f"{c['id']} · H={c['hb']:.1f} m",linewidth=3 if c is selected else 1.3)
        for name,key in [('Bocatoma','intake'),('Cámara','chamber'),('Turbina','tail')]:
            p=selected[key];ax.scatter(p.x,p.y,s=60);ax.annotate(name,(p.x,p.y),xytext=(8,6),textcoords='offset points',fontsize=10)
        north=streams[streams.id==2];north.plot(ax=ax,color='#edb346',linewidth=3)
        ax.legend();ax.set_aspect('equal');ax.set_title('La Cantina · revisión 2 · arroyo norte incluido sin recorte predial');fig.savefig(OUT/'qa_ubicaciones.png',dpi=150,bbox_inches='tight');plt.close(fig)
        fig,ax=plt.subplots(figsize=(11,4));rp=selected['route_profile'];ss=np.array([x['distance_m'] for x in rp]);zz=np.array([x['terrain_m'] for x in rp]);ax.plot(ss,zz,label='Terreno DTM');ax.plot(ss,zz-1,label='Eje supuesto enterrado 1 m',linestyle=':')
        ax.plot(ss,selected['chamber_z']-scenarios[-1]['hf_m']*ss/ss[-1],label='Línea piezométrica, 100 L/s');ax.set_xlabel('Distancia horizontal (m)');ax.set_ylabel('Cota DTM (m)');ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(OUT/'perfil_tuberia.png',dpi=150);plt.close(fig)
        print(json.dumps(metadata,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
