"""Construye index.html Folium con datos, imágenes y KMZ incorporados."""
from pathlib import Path
import json, base64, io, zipfile, html, shutil, math
import xml.etree.ElementTree as ET
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject, transform_bounds
from PIL import Image
import folium
from folium.plugins import MeasureControl, Fullscreen, MousePosition
from branca.colormap import LinearColormap
from branca.element import MacroElement, Template
from hydraulics import ETA, CAPACITY_FACTOR, HW_C, MINOR_K

ROOT=Path(__file__).parent;OUT=ROOT/'outputs';DIST=ROOT/'sites/la-cantina-hidro/dist'
DIST.mkdir(parents=True,exist_ok=True)

def png_overlay(path,maxsize=1400):
    cache=OUT/(path.stem+'_web.png');meta=cache.with_suffix('.json')
    if cache.exists() and meta.exists():return cache,json.loads(meta.read_text())
    with rasterio.open(path) as src:
        factor=max(src.width,src.height)/maxsize
        sw,sh=round(src.width/factor),round(src.height/factor)
        arr=src.read(out_shape=(src.count,sh,sw),resampling=Resampling.bilinear)
        src_tr=src.transform*src.transform.scale(src.width/sw,src.height/sh)
        dst_tr,dw,dh=calculate_default_transform(src.crs,3857,sw,sh,*src.bounds)
        dest=np.zeros((4,dh,dw),dtype='uint8')
        for b in range(min(4,src.count)):
            reproject(arr[b],dest[b],src_transform=src_tr,src_crs=src.crs,dst_transform=dst_tr,dst_crs=3857,resampling=Resampling.bilinear)
        if src.count<4:dest[3]=255
        left,bot,right,top=rasterio.transform.array_bounds(dh,dw,dst_tr)
        wb=transform_bounds(3857,4326,left,bot,right,top)
        bounds=[[wb[1],wb[0]],[wb[3],wb[2]]]
        Image.fromarray(np.moveaxis(dest,0,2),'RGBA').save(cache,optimize=True)
        meta.write_text(json.dumps(bounds))
        return cache,bounds

def kmz_bytes(proposal,selected):
    ns='http://www.opengis.net/kml/2.2';ET.register_namespace('',ns)
    def e(tag,parent,text=None):
        a=ET.SubElement(parent,'{'+ns+'}'+tag)
        if text is not None:a.text=str(text)
        return a
    root=ET.Element('{'+ns+'}kml');doc=e('Document',root);e('name',doc,'La Cantina · propuesta preliminar '+selected['id'])
    e('description',doc,'Cotas y trazados conceptuales derivados del DTM. Sin aforo. Validar captación, restitución, inundación, servidumbres y niveles de agua en terreno. Altitudes relativas al terreno; no usar como levantamiento de obra.')
    for _,r in proposal.iterrows():
        pm=e('Placemark',doc);e('name',pm,r['name']);style=e('Style',pm);ls=e('LineStyle',style);e('color',ls,'ff2788ff');e('width',ls,4)
        if r.geometry.geom_type=='Point':
            g=e('Point',pm);e('altitudeMode',g,'clampToGround');e('coordinates',g,f'{r.geometry.x},{r.geometry.y},0')
        else:
            g=e('LineString',pm);e('tessellate',g,1);e('altitudeMode',g,'clampToGround');e('coordinates',g,' '.join(f'{x},{y},0' for x,y in r.geometry.coords))
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('doc.kml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
    return data.getvalue()

def main():
    r=json.loads((OUT/'results.json').read_text(encoding='utf8'));sel=r['selected']
    geo={name:json.loads((OUT/(name+'.geojson')).read_text(encoding='utf8')) for name in ['lotes','caminos','deslinde','hidrografia','curvas','alternativas','propuesta','cobertura']}
    lots=gpd.read_file(OUT/'lotes.geojson');bd=gpd.read_file(OUT/'deslinde.geojson')
    c=lots.to_crs(32718).geometry.union_all().centroid
    cp=gpd.GeoSeries([c],crs=32718).to_crs(4326).iloc[0]
    m=folium.Map(location=[cp.y,cp.x],zoom_start=16,tiles=None,control_scale=True,prefer_canvas=True,zoom_control=False)
    folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',name='Satélite · Esri World Imagery',attr='Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',max_zoom=22,max_native_zoom=19).add_to(m)
    folium.TileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',name='Relieve · OpenTopoMap',attr='Map data © OpenStreetMap contributors, SRTM | Map style © OpenTopoMap (CC-BY-SA)',max_zoom=22,max_native_zoom=17,show=False).add_to(m)
    # Ortofotos incorporadas: funcionan incluso si los fondos remotos fallan.
    for name,path,show,size in [('Ortomosaico 10 cm · vista web reducida',ROOT/'LA_CANTINA_GSD10_EXTENT.tif',True,1400),('Ortomosaico completo · vista web reducida',ROOT/'LA_CANTINA_transparent_mosaic_group1.tif',False,1700)]:
        png,bounds=png_overlay(path,size)
        folium.raster_layers.ImageOverlay(str(png),bounds=bounds,name=name,opacity=.95,show=show,interactive=True,attr='Ortomosaico proporcionado por el propietario · remuestreado para web').add_to(m)
    folium.GeoJson(geo['deslinde'],name='Deslinde original · 104,57 ha',style_function=lambda f:dict(color='#f7f6ec',weight=3,fillOpacity=0,dashArray='8 5'),tooltip='Deslinde original (KML proporcionado)').add_to(m)
    folium.GeoJson(geo['cobertura'],name='Cobertura válida del DTM · 50,6% del predio',show=False,style_function=lambda f:dict(color='#e0af48',weight=2,fillColor='#e0af48',fillOpacity=.12),tooltip='Área con datos DTM: no se extrapolan cotas fuera de ella').add_to(m)
    pal=['#57bda9','#f2c970','#87b6d9','#c9a6cf','#f39975']
    for i,f in enumerate(geo['lotes']['features']):f['properties']['color']=pal[i%len(pal)]
    folium.GeoJson(geo['lotes'],name='Lotes de subdivisión · 10',style_function=lambda f:dict(color=f['properties']['color'],weight=2,fillColor=f['properties']['color'],fillOpacity=.19),highlight_function=lambda f:dict(weight=4,fillOpacity=.35),tooltip=folium.GeoJsonTooltip(fields=['name'],aliases=['Lote'],sticky=False)).add_to(m)
    labels=folium.FeatureGroup(name='Etiquetas de lotes',show=True).add_to(m)
    for _,lot in lots.iterrows():
        p=lot.geometry.representative_point();folium.Marker([p.y,p.x],icon=folium.DivIcon(html=f'<span class="lot-label">{html.escape(lot["name"])}</span>')).add_to(labels)
    folium.GeoJson(geo['caminos'],name='Camino vehicular',style_function=lambda f:dict(color='#d1c0a4',weight=1,fillColor='#c3b69e',fillOpacity=.6),tooltip='Camino vehicular según subdivisión').add_to(m)
    for f in geo['hidrografia']['features']:f['properties']['regimen']='Permanente, según propietario' if f['properties']['tipo']=='arroyo' else 'Bajo caudal; posible tramo subterráneo'
    folium.GeoJson(geo['hidrografia'],name='Arroyos y quebradas',style_function=lambda f:dict(color='#37c4ef' if f['properties']['tipo']=='arroyo' else '#99ced4',weight=3,dashArray=None if f['properties']['tipo']=='arroyo' else '6 5'),tooltip=folium.GeoJsonTooltip(fields=['id','tipo','regimen'],aliases=['Cauce','Tipo','Referencia hidrológica'])).add_to(m)
    zs=[f['properties']['Elevation'] for f in geo['curvas']['features']];cmap=LinearColormap(['#3fa4bf','#65c18c','#ebdc73','#d28a50','#a25b67'],vmin=min(zs),vmax=max(zs))
    folium.GeoJson(geo['curvas'],name='Curvas de nivel · intervalo 1 m',show=False,style_function=lambda f:dict(color=cmap(f['properties']['Elevation']),weight=1.3 if f['properties']['Elevation']%5==0 else .65,opacity=.85),tooltip=folium.GeoJsonTooltip(fields=['Elevation'],aliases=['Cota DTM (m)'])).add_to(m)
    groups={}
    for cand in r['alternatives']:
        cid=cand['id'];active=cid==sel['id'];color='#ff9c4b' if cand['tipo']=='arroyo' else '#d09ce5'
        group=folium.FeatureGroup(name=f"{cid} · {cand['tipo']} · H {cand['hb']:.1f} m"+(' · revisar perfil' if not cand['hgl_ok'] else ''),show=active).add_to(m);groups[cid]=group.get_name()
        feat=next(f for f in geo['alternativas']['features'] if f['properties']['candidate']==cid)
        folium.GeoJson(feat,style_function=lambda f,col=color:dict(color=col,weight=5,opacity=.95),tooltip=f"{cid} · Tubería {cand['length_m']:.1f} m · trazado conceptual").add_to(group)
        folium.GeoJson(cand['adduction_geojson'],style_function=lambda f:dict(color='#f2db86',weight=4,dashArray='5 4'),tooltip=f"Aducción conceptual · {cand['adduction_length_m']:.1f} m").add_to(group)
        for key,title,zkey,letter in [('intake','Bocatoma','intake_z','B'),('chamber','Cámara de carga','chamber_z','C'),('tail','Turbina / restitución','tail_z','T')]:
            lon,lat=cand['points_wgs84'][key]
            popup=f"<b>{title} · {cid}</b><br>Cota del terreno: {cand[zkey]:.2f} m<br>Lat: {lat:.7f} · Lon: {lon:.7f}<br><small>Ubicación conceptual. Nivel de agua, inundación y emplazamiento de obra pendientes de terreno.</small>"
            folium.Marker([lat,lon],tooltip=title,icon=folium.DivIcon(html=f'<span class="site-pin" style="border-color:{color}">{letter}</span>'),popup=folium.Popup(popup,max_width=280)).add_to(group)
    folium.LayerControl(position='topright',collapsed=True).add_to(m)
    Fullscreen(position='topright',title='Pantalla completa').add_to(m)
    MeasureControl(position='topright',primary_length_unit='meters',secondary_length_unit='kilometers',primary_area_unit='hectares').add_to(m)
    MousePosition(position='bottomright',separator=' · ',prefix='WGS84',num_digits=6).add_to(m)
    kmz=kmz_bytes(gpd.read_file(OUT/'propuesta.geojson'),sel);(OUT/'la_cantina_propuesta.kmz').write_bytes(kmz)
    # KMZ, CSV y JSON incorporados para conservar el archivo único.
    payload=dict(results=r,groups=groups,map_name=m.get_name(),kmz=base64.b64encode(kmz).decode(),
                 csv=base64.b64encode((OUT/'escenarios.csv').read_bytes()).decode(),
                 geojson=base64.b64encode((OUT/'propuesta.geojson').read_bytes()).decode())
    panel=(ROOT/'viewer_panel.html').read_text(encoding='utf8').replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=False).replace('</','<\\/'))
    m.get_root().html.add_child(folium.Element(panel.split('<!--SCRIPT-->')[0]))
    behavior=MacroElement()
    behavior._template=Template('{% macro script(this, kwargs) %}'+panel.split('<!--SCRIPT-->')[1]+'{% endmacro %}')
    m.add_child(behavior)
    m.get_root().header.add_child(folium.Element('<title>La Cantina | Atlas hidroeléctrico</title><meta name="description" content="Prefactibilidad hidroeléctrica: lotes, topografía, alternativas y escenarios de generación.">'))
    m.save(DIST/'index.html');shutil.copy2(DIST/'index.html',ROOT/'index.html')
    for name in ['la_cantina_propuesta.kmz','escenarios.csv','results.json','propuesta.geojson','perfil_tuberia.png']:
        shutil.copy2(OUT/name,DIST/name)
    print('Visor generado:',DIST/'index.html','MB:',round((DIST/'index.html').stat().st_size/1e6,2))

if __name__=='__main__':main()
