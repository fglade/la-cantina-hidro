from analyze import *
lots=read_kml(ROOT/'20260408_parelas_caminas_kml.kml').to_crs(CRS)
boundary=read_kml(ROOT/'20231207_deslinde_original.kml').to_crs(CRS)
s=gpd.read_file(ROOT/'hidro.shp').to_crs(CRS)
with rasterio.open(ROOT/'LA_CANTINA_dtm.tif') as d:
    fig,ax=plt.subplots(figsize=(12,12));z=d.read(1,masked=True)
    ax.imshow(z,extent=(d.bounds.left,d.bounds.right,d.bounds.bottom,d.bounds.top),cmap='terrain')
    boundary.boundary.plot(ax=ax,color='black');lots.boundary.plot(ax=ax,color='white')
    for _,r in s.iterrows():
        coords=[r.geometry.interpolate(float(t)) for t in np.linspace(0,r.geometry.length,100)]
        vals=np.array([v[0] if not np.ma.is_masked(v[0]) else np.nan for v in d.sample([(p.x,p.y) for p in coords],masked=True)])
        valid=vals[np.isfinite(vals)&(vals>-9999)]
        print(r.id,r.tipo,'nvalid',len(valid),'range',valid.min() if len(valid) else None,valid.max() if len(valid) else None,'length',r.geometry.length,'ends',vals[0],vals[-1],flush=True)
        print('inside',r.geometry.intersection(boundary.geometry.union_all()).length,flush=True)
        xs,ys=r.geometry.xy;ax.plot(xs,ys,label=f'{r.id} {r.tipo}');p=r.geometry.interpolate(.5,normalized=True);ax.text(p.x,p.y,str(r.id),fontsize=14)
    ax.legend();ax.set_aspect('equal');fig.savefig(OUT/'exploracion.png',dpi=120,bbox_inches='tight')
