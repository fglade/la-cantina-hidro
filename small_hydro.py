"""Tres pares cortos de captación/turbina para 0,5–1 kW estacional."""
from pathlib import Path
import json,math,csv
import numpy as np
import geopandas as gpd
import rasterio
from scipy.optimize import brentq
from shapely.geometry import Point,LineString
from shapely.ops import substring
from inspect_data import read_kml
from hydraulics import hazen_williams

ROOT=Path(__file__).parent;OUT=ROOT/'outputs'
OD_MM=(40,50,63,75,90,110,125)

def design(target_kw,hb,length,profile,cap_z):
    """PE100 SDR11/PN16 idealizado; caudal útil, después de reservas."""
    for od in OD_MM:
        d=od/1000*(1-2/11)
        def calc(q):
            v=4*q/(math.pi*d*d);hf=hazen_williams(q,d,length);hm=3*v*v/(2*9.81);hn=hb-hf-hm
            return 9.81*q*hn*.65,v,hf,hm,hn
        # Restringe pérdidas totales al 10% y velocidad a 2,5 m/s.
        qmax=min(.025,2.5*math.pi*d*d/4)
        while calc(qmax)[2]+calc(qmax)[3]>.1*hb:qmax*=.95
        if calc(qmax)[0]<target_kw:continue
        q=brentq(lambda q:calc(q)[0]-target_kw,1e-8,qmax)
        p,v,hf,hm,hn=calc(q);end=profile[-1]['distance_m']
        clearance=min(cap_z-hf*x['distance_m']/end-(x['terrain_m']-.5) for x in profile)
        if clearance<0:continue
        return dict(target_kw=target_kw,power_kw=p,q_ls=q*1000,pipe_od_mm=od,pipe_id_mm=d*1000,
                    assumed_sdr=11,assumed_pn_bar=16,velocity_ms=v,hf_m=hf,hm_m=hm,net_head_m=hn,
                    gross_head_m=hb,min_hgl_clearance_m=clearance,burial_depth_m=.5,
                    daily_gross_kwh=p*24,daily_usable_kwh=p*24*.8*.9,
                    season_60d_usable_kwh=p*24*.8*.9*60,
                    nozzle_ideal_mm=1000*math.sqrt(4*q/(math.pi*math.sqrt(2*9.81*hn))))
    return None

def main():
    streams=gpd.read_file(ROOT/'hidro.shp').to_crs(32718)
    lots=read_kml(ROOT/'20260408_parelas_caminas_kml.kml').to_crs(32718)
    lots=lots[lots.name.str.fullmatch(r'\d+')]
    inner=lots.geometry.map(lambda g:g.buffer(-4)).union_all()
    boundary=read_kml(ROOT/'20231207_deslinde_original.kml').to_crs(32718).geometry.union_all()
    hub=Point(json.loads((OUT/'rotonda.json').read_text(encoding='utf8'))['center_utm'])
    with rasterio.open(ROOT/'LA_CANTINA_dtm.tif') as dem:
        arr=dem.read(1)
        def sample(points):
            xy=np.array([(p.x,p.y) for p in points]);cols=np.floor((xy[:,0]-dem.transform.c)/dem.transform.a).astype(int);rows=np.floor((xy[:,1]-dem.transform.f)/dem.transform.e).astype(int)
            valid=(rows>=0)&(rows<dem.height)&(cols>=0)&(cols<dem.width);vals=np.full(len(points),np.nan)
            vals[valid]=arr[rows[valid],cols[valid]];vals[vals<=-9999]=np.nan;return vals
        rough=[]
        for _,s in streams[streams.tipo=='arroyo'].iterrows():
            line=s.geometry;ds=np.arange(0,line.length,10.);pts=[line.interpolate(float(t)) for t in ds];zz=sample(pts)
            if np.isfinite(zz).sum()<4:continue
            vi=np.flatnonzero(np.isfinite(zz))
            if zz[vi[0]]<zz[vi[-1]]:
                line=LineString(list(line.coords)[::-1]);pts=[line.interpolate(float(t)) for t in ds];zz=sample(pts)
            for i in range(len(ds)):
                if not np.isfinite(zz[i]):continue
                for j in range(i+4,min(i+25,len(ds))):
                    if not np.isfinite(zz[i:j+1]).all():continue
                    hb=float(zz[i]-zz[j]);distance=pts[i].distance(pts[j])
                    if not 18<=hb<=70 or distance<25:continue
                    pipe=LineString([pts[i],pts[j]])
                    if pipe.intersection(inner).length>5:continue
                    cable=pts[j].distance(hub)*1.25
                    outside=pipe.difference(boundary).length
                    # Costos relativos de material/montaje; no monetiza servidumbre.
                    score=distance*1.5+cable*.6+outside*.8+max(hb-55,0)*5
                    rough.append(dict(stream_id=int(s.id),hb=hb,intake=pts[i],tail=pts[j],straight=pipe,
                                      channel=substring(line,float(ds[i]),float(ds[j])),score=score,cable_length_allowance_m=cable))
        rough.sort(key=lambda c:c['score']);evaluated=[]
        # Evalúa una muestra espacialmente diversa, no sólo variantes vecinas.
        seeds=[]
        for c in rough:
            if any(c['stream_id']==e['stream_id'] and c['intake'].distance(e['intake'])<25 and c['tail'].distance(e['tail'])<25 for e in seeds):continue
            seeds.append(c)
            if len(seeds)>=90:break
        for c in seeds:
            for pipe in [c['straight'],c['channel']]:
                ss=np.linspace(0,pipe.length,max(3,math.ceil(pipe.length/1.5)+1));pts=[pipe.interpolate(float(t)) for t in ss];zs=sample(pts)
                if not np.isfinite(zs).all() or pipe.intersection(inner).length>5:continue
                L=float(np.hypot(np.diff(ss),np.diff(zs)).sum())
                rp=[dict(distance_m=float(t),terrain_m=float(z)) for t,z in zip(ss,zs)]
                spec=design(1.,c['hb'],L,rp,float(zs[0]))
                if spec is None:continue
                c=dict(c,route=pipe,profile=rp,length_m=L,length_plan_m=pipe.length,intake_z=float(zs[0]),tail_z=float(zs[-1]),design=spec)
                c['score']=L*1.5+c['cable_length_allowance_m']*.6+pipe.difference(boundary).length*.8+max(c['hb']-55,0)*5
                evaluated.append(c);break
        evaluated.sort(key=lambda c:c['score'])
        selected=[]
        # Asegura una comparación entre arroyo norte y límite sur.
        for sid in (2,1):
            choices=[c for c in evaluated if c['stream_id']==sid]
            if choices:selected.append(choices[0])
        for c in evaluated:
            if all(c['intake'].distance(e['intake'])>65 or c['tail'].distance(e['tail'])>65 for e in selected):selected.append(c);break
        print('Candidatos',len(rough),'semillas',len(seeds),'evaluados',len(evaluated),'seleccionados',len(selected),flush=True)
        if len(selected)!=3:raise RuntimeError('No hay tres sitios distintos con perfil aceptable.')
        selected.sort(key=lambda c:c['score']);output=[];features=[]
        for rank,c in enumerate(selected,1):
            cid=f'S{rank}';name=('Arroyo norte' if c['stream_id']==2 else 'Arroyo límite sur')
            def wgs(g):return gpd.GeoSeries([g],crs=32718).to_crs(4326).iloc[0]
            outside=c['route'].difference(boundary).length
            plans=[design(t,c['hb'],c['length_m'],c['profile'],c['intake_z']) for t in (.5,1.)]
            item=dict(id=cid,rank=rank,stream_id=c['stream_id'],stream_name=name,priority=1,
                      intake_wgs84=list(wgs(c['intake']).coords)[0],turbine_wgs84=list(wgs(c['tail']).coords)[0],
                      intake_z=c['intake_z'],turbine_z=c['tail_z'],gross_head_m=c['hb'],
                      length_m=c['length_m'],length_plan_m=c['length_plan_m'],outside_property_plan_m=outside,
                      inside_points={k:boundary.buffer(.001).covers(c[key]) for k,key in [('intake','intake'),('turbine','tail')]},
                      cable_length_allowance_m=c['cable_length_allowance_m'],cable_basis='1,25×distancia recta a rotonda; no es trazado eléctrico levantado',
                      route_profile=c['profile'],plans=plans,score=c['score'],
                      static_pressure_bar=float((c['intake_z']-min(x['terrain_m']-.5 for x in c['profile']))*.0980665),
                      turbine_family='Pelton de baja potencia, 1 chorro; confirmar curva fabricante',
                      intake_scheme='Captación compacta con rejilla y desarenado/venteo en cabecera; sin canal ni cámara separada',
                      ranking_basis='Comparación de longitud 3D, cable estimado a rotonda, exterioridad y presión; no máxima potencia ni óptimo global')
            output.append(item)
            for title,geom in [('Bocatoma compacta',c['intake']),('Turbina y restitución',c['tail']),('Tubería propuesta',c['route'])]:features.append(dict(site=cid,name=title,stream=name,geometry=geom))
        (OUT/'microhidro_tres_sitios.json').write_text(json.dumps(dict(selected=output[0]['id'],sites=output,
                    household_count=3,season_days=60,assumed_daily_load_kwh_per_house=[1.5,3.],total_daily_load_kwh=[4.5,9.],
                    exclusions='Sin calefacción, termo eléctrico, cocina eléctrica ni carga de vehículos; simultaneidad por definir.',
                    recommended_generation_kw=1.,recommended_battery_nominal_kwh=5.12,recommended_inverter_continuous_kw=3.,
                    inverter_limit='3 kW compartidos entre casas; no 3 kW por casa. Un solo termo o hervidor puede superar el régimen previsto.',
                    estimated_usable_battery_kwh=5.12*.8*.9),ensure_ascii=False,indent=2),encoding='utf8')
        gpd.GeoDataFrame(features,crs=32718).to_crs(4326).to_file(OUT/'microhidro_tres_sitios.geojson',driver='GeoJSON')
        print([(x['id'],x['stream_name'],round(x['gross_head_m'],1),round(x['length_m'],1),round(x['outside_property_plan_m'],1),x['plans']) for x in output],flush=True)

if __name__=='__main__':main()
