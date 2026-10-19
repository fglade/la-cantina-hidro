import json
from pathlib import Path
import geopandas as gpd
import rasterio
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon, LineString

ROOT=Path(__file__).parent
def read_kml(path):
    ns={'k':'http://www.opengis.net/kml/2.2'}
    rows=[]
    for pm in ET.parse(path).findall('.//k:Placemark',ns):
        name=pm.findtext('k:name','',ns)
        for tag,cls in [('Polygon',Polygon),('LineString',LineString)]:
            for e in pm.findall('.//k:'+tag,ns):
                coords=e.find('.//k:coordinates',ns).text
                xy=[tuple(map(float,c.split(',')[:2])) for c in coords.split()]
                rows.append({'name':name,'geometry':cls(xy)})
    return gpd.GeoDataFrame(rows,crs=4326)

if __name__=='__main__':
    for p in ROOT.glob('*.kml'):
        g=read_kml(p)
        print(p.name,g[['name']].to_dict('records'),g.geom_type.to_list(),g.total_bounds.tolist())
    for p in ROOT.glob('*.shp'):
        g=gpd.read_file(p)
        print(p.name,'CRS',g.crs,'count',len(g),'bounds',g.total_bounds.tolist(),'fields',g.drop(columns='geometry').head(8).to_dict('records'))
    for p in ROOT.glob('*.tif'):
        with rasterio.open(p) as r:
            print(p.name,'CRS',r.crs,'shape',r.shape,'res',r.res,'bounds',r.bounds,'nodata',r.nodata,'bands',r.count,'dtype',r.dtypes)
