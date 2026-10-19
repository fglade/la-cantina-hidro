"""Informe, presupuesto y figuras de la revisión 3."""
from pathlib import Path
import json, shutil, csv
import numpy as np
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import rasterio
from rasterio.enums import Resampling
ROOT=Path(__file__).parent;OUT=ROOT/'outputs';DIST=ROOT/'sites/la-cantina-hidro/dist'
F=lambda n,d=1:f'{n:,.{d}f}'.replace(',','X').replace('.',',').replace('X','.')
M=lambda n:F(n/1e6,1)

def main():
    small=json.loads((OUT/'microhidro_tres_sitios.json').read_text(encoding='utf8'));sites=small['sites']
    road=json.loads((OUT/'camino_propuesto.json').read_text(encoding='utf8'));fin=json.loads((OUT/'presupuesto_productos.json').read_text(encoding='utf8'))
    rows='\n'.join(f"| {s['id']} · {s['stream_name']} | {F(s['gross_head_m'])} | {F(s['length_m'])} | {F(s['plans'][1]['net_head_m'])} | {F(s['plans'][1]['q_ls'],2)} | {s['plans'][1]['pipe_od_mm']} / {F(s['plans'][1]['pipe_id_mm'])} | {F(s['outside_property_plan_m'])} |" for s in sites)
    coords='\n'.join(f"| {s['id']} | {name} | {s[key][1]:.7f} | {s[key][0]:.7f} | {F(s[z])} |" for s in sites for key,name,z in [('intake_wgs84','Bocatoma','intake_z'),('turbine_wgs84','Turbina/restitución','turbine_z')])
    costs='\n'.join(f"| {sid} | {M(b['total_low_clp'])}–{M(b['total_high_clp'])} | {b['cable_section_mm2']} | {F(next(s for s in sites if s['id']==sid)['cable_length_allowance_m'],0)} | {F(b['cable_voltage_drop_pct'])}% |" for sid,b in fin['budgets'].items())
    b=fin['budgets']['S1'];rb=fin['road'];s=sites[0];p=s['plans'][1]
    boq='\n'.join(f"| {x['item']} | {F(x['quantity'],1)} | {M(x['low_clp'])} | {M(x['high_clp'])} | {x['basis']} |" for x in b['items'])
    rboq='\n'.join(f"| {x['item']} | {F(x['quantity'],0)} | {F(x['unit_low_clp'],0)}–{F(x['unit_high_clp'],0)} | {M(x['low_clp'])}–{M(x['high_clp'])} |" for x in rb['items'])
    products='\n'.join(f"- [{x['name']}]({x['url']}): {x['price']}. {x['verdict']} [Referencia consultada]({x['reference']})." for x in fin['products'])
    sources='\n'.join(f"- [{x['item']}]({x['url']}): {x['observed']}" for x in fin['sources'])
    impacts='; '.join(f"lote {x['lote']}: {F(x['corridor_area_m2'],0)} m² de plataforma y {F(x['axis_length_m'])} m de eje interior" for x in road['lot_impacts'])
    text=f'''# La Cantina · acceso nuevo y microhidro para verano

Revisión 3 · 19 de octubre de 2026. Propuesta conceptual con herramientas gratuitas. [Visor público](https://la-cantina-hidro.craftysmile14.chatgpt.site) · [Repositorio](https://github.com/fglade/la-cantina-hidro).

**Propuesta eléctrica: 1 kW continuo, batería nominal de 5,12 kWh e inversor de 3 kW compartidos para 2–3 casas de consumo básico durante unos 60 días de verano.** Primera alternativa a aforar: **S1, arroyo norte**, con unos {F(s['length_m'])} m de tubería. El alimentador a rotonda eleva el costo: energía S1 **${M(b['total_low_clp'])}–{M(b['total_high_clp'])} millones CLP**, con 25% de contingencia y sin camino ni servidumbres/tasas específicas.

**El acceso vial es otra escala de inversión.** Se propone un corredor nuevo de **{F(road['length_plan_m'],0)} m**, desde la desembocadura del arroyo del límite sur hasta la rotonda inferida del loteo. Rasante de cálculo ≤10%, pero con movimiento de tierras y afectación de lotes. Presupuesto de orden de magnitud: **${M(rb['total_low_clp'])}–{M(rb['total_high_clp'])} millones**, con 30% de contingencia. No es un límite superior ni una cotización. S1 + camino: **${M(rb['total_low_clp']+b['total_low_clp'])}–{M(rb['total_high_clp']+b['total_high_clp'])} millones** bajo estos alcances. No corresponde presentar todo como una instalación barata y sin maquinaria.

## Alcance y cambio de criterio

Se excluye por completo la geometría CAMINOS entregada como apoyo de trazado, costo o evidencia de obra existente. Sólo se usan los diez polígonos numerados para el loteo. Los archivos originales se preservan por trazabilidad. La rotonda se localiza ajustando un círculo a 60 vértices de arcos de linderos de lotes: radio inferido 25,98 m; no se usa el polígono CAMINOS.

Se mantienen completos los seis cauces y las 512 curvas, incluidos el arroyo norte y la topografía exterior al deslinde. Arroyos permanentes según el propietario: prioridad 1. Quebradas no permanentes: última prioridad; el propietario indica que habría que perforar para alcanzar el agua. No se les atribuye generación firme ni se propone perforar para esta microcentral.

El [apéndice de potencial amplio](APENDICE_POTENCIAL.md) conserva los escenarios originales de 10/25/50/100 L/s, recalculados sin preferencia por caminos hipotéticos. Esa selección de mayor salto no es el proyecto pequeño recomendado aquí.

## Demanda y tamaño sugerido

Supuesto de trabajo, no inventario de aparatos: 1,5–3 kWh/casa/día para iluminación LED, refrigeración eficiente, comunicaciones y equipos pequeños. Tres casas: 4,5–9 kWh/día. Sin calefacción eléctrica, termo, cocina eléctrica ni carga de vehículos. La ubicación y simultaneidad de las casas aún no se conocen.

| Generación continua | Energía bruta diaria | Útil diaria supuesta | Útil en 30 días | Útil en 60 días |
|---:|---:|---:|---:|---:|
| 0,5 kW | 12 kWh | 8,64 kWh | 259,2 kWh | 518,4 kWh |
| 1,0 kW | 24 kWh | 17,28 kWh | 518,4 kWh | 1.036,8 kWh |

Útil = P × horas × 0,80 disponibilidad × 0,90 almacenamiento/distribución, ambos supuestos. No es una predicción de caudal de verano. No sumar otra vez esos descuentos al comparar con la demanda. 0,5 kW puede quedar justo para tres casas; 1 kW da margen para cargas moderadas y recarga. No se garantiza la demanda sin medir caudal y levantar consumos.

Batería LiFePO4: 5,12 kWh nominales, unos 3,69 kWh útiles adoptando 80% de descarga y 90% de entrega; no ofrece un día entero a la demanda superior. Inversor senoidal de 3 kW **compartidos**, no por casa. Su potencia debe confirmarse con arranque de refrigeradores y gestión de simultaneidad. No transportar 1 kW a 48 V por cientos de metros: la arquitectura de generación, regulación y transporte debe definirla el proyectista eléctrico.

## Tres pares prioritarios para aforo y visita

Todos dimensionados aquí a **1 kW eléctrico** con η global 0,65. Son tres alternativas, no tres instalaciones acumulativas.

| Par / cauce | Hb m | Tubería 3D m | Hn m | Q útil L/s | HDPE exterior / interior mm | Tubería exterior al deslinde, planta m |
|---|---:|---:|---:|---:|---:|---:|
{rows}

**S1:** primer candidato por menor salto, tubo corto y menor provisión de cable que las otras alternativas seleccionadas. **S2:** reserva en el norte, menor salto y más caudal necesario. **S3:** comparación en el arroyo sur; mayor distancia eléctrica estimada a la rotonda. El ranking usa longitudes de tubo/cable, presión y exterioridad; no demuestra óptimo global ni acceso fácil para construir. La accesibilidad de obras y costos de servidumbre no están acreditados.

**Los tres pares están fuera del deslinde original.** Estudiar el arroyo norte no concede acceso ni uso del terreno. No comprar equipos antes de comprobar acceso/tenencia y caudal derivable en verano después de reservas y otros usos.

| Par | Referencia | Latitud | Longitud | Cota terreno m |
|---|---|---:|---:|---:|
{coords}

Coordenadas EPSG:4326; distancias calculadas en EPSG:32718. Los puntos son referencias sobre el cauce, no emplazamientos constructivos. Ubicar la sala en una margen segura frente a crecidas y verificar restitución. El DTM proporciona cotas de terreno, no niveles del agua; el datum vertical y alineación del cauce necesitan comprobación. El salto real puede variar.

## Hidráulica compacta para S1

Captación con rejilla, desarenado y venteo/cabezal que mantenga la tubería llena; sin canal de aducción ni cámara separada en esta propuesta compacta. Incorporar anclajes, cierre controlado y restitución; no modelar un azud importante como si fuera una simple manguera.

Hb = {F(s['intake_z'],2)} − {F(s['turbine_z'],2)} = **{F(s['gross_head_m'],2)} m**. Con HDPE PE100 PN16 SDR11 idealizado de diámetro exterior {p['pipe_od_mm']} mm e interior **{F(p['pipe_id_mm'],2)} mm** ({F(p['pipe_id_mm']/25.4,2)} pulgadas interiores), Q = {F(p['q_ls'],3)} L/s y L 3D = {F(s['length_m'],2)} m:

- Hazen–Williams: hf = 10,67 L Q^1,852 / (145^1,852 D^4,8704) = **{F(p['hf_m'],3)} m**, con Q en m³/s y D interior en m.
- Pérdidas locales: hm = K v²/(2g), K=3 supuesto → **{F(p['hm_m'],3)} m**.
- Hn = Hb − hf − hm = **{F(p['net_head_m'],3)} m**; pérdidas totales {F((p['hf_m']+p['hm_m'])/s['gross_head_m']*100)}%, menores al 10% adoptado.
- P = 9,81 × {p['q_ls']/1000:.6f} × {p['net_head_m']:.3f} × 0,65 ≈ **1 kW**. El caudal es requisito de diseño, no dato aforado.

También se calculan planes de 0,5 kW por sitio. Se comprueban pérdidas totales ≤10%Hb, velocidad ≤2,5 m/s y perfil preliminar bajo línea piezométrica con 0,5 m de enterramiento supuesto. Diámetro interior idealizado: validar espesor/tolerancia comercial. No se comprueban golpe de ariete, válvulas reales, enterramiento de obra ni estabilidad de laderas. La eficiencia adoptada puede ser optimista para equipos muy baratos; exigir rendimiento del conjunto en ese punto H/Q.

## Propuesta de turbina y búsqueda en AliExpress

Preferencia técnica: **Pelton compacta de aproximadamente 1 kW a H neto 24,3 m y Q útil 6,46 L/s**, ajustada por fabricante. Un Turgo puede ser alternativa si su curva encaja. La elección no se hace sólo por los kW del anuncio ni por el máximo caudal de otra condición de salto.

El acceso automatizado directo a AliExpress fue bloqueado. Se entregan enlaces identificados mediante referencias públicas consultadas previamente, con precios históricos claramente separados de una cotización actual. **No se ha verificado variante, curva H/Q, stock, envío ni precio puesto en Chile; no hay un anuncio confirmado como compra adecuada.**

{products}

La ficha oficial de [PowerSpout PLT](https://www.powerspout.com/products/powerspout-plt) ofrece una referencia Pelton documentada y precio en NZD antes de GST; pedir configuración para el punto S1 y costo puesto en Chile. La alternativa [Turgo TRG](https://www.powerspout.com/pages/turgo-trg-info) declara rango de salto 2–30 m y caudales 8–16 L/s; S1 requiere menos caudal, por lo que no se adopta automáticamente. No se afirma que la potencia máxima de catálogo se alcance en este sitio.

Especificación para solicitar oferta, sin contactar vendedores desde este estudio: potencia **entregada** de 1 kW a Hn24,3 m/Q6,46 L/s; curva de rendimiento a carga parcial; generador y boquillas incluidos; tensión seleccionada según transporte y cargador; 50 Hz si salida AC; regulación ante desconexión de carga, protección de sobrevelocidad y carga de desvío; repuestos, peso, dimensiones y costo final entregado en Chile. Un rodete suelto o un generador axial sin curva no satisface esa especificación.

## Presupuesto eléctrico, separado del camino

Montos CLP de orden de magnitud con provisiones, no ofertas. Valores publicados sólo anclan algunas partidas; obra, transporte y puesta en marcha no tienen cotización local. Las provisiones buscan contemplar IVA/logística, sin cálculo tributario definitivo. Se añade 25% a los subtotales. No se monetizan acceso a terrenos, derechos, tasas ni obras mayores imprevistas.

| Sitio | Total energía $M, +25% | Cable preliminar mm² | Longitud estimada a rotonda m | Caída resistiva orientativa |
|---|---:|---:|---:|---:|
{costs}

Cable estimado = 1,25×distancia recta a rotonda; **no hay traza eléctrica levantada**. Caída a 230 V AC monofásico, 1 kW, FP1 y resistividad caliente 0,0225 Ωmm²/m. No verifica ampacidad, arranques, protecciones, puesta a tierra ni ramales a casas. El inversor estará cerca del nodo de consumo para no transportar sus picos por este alimentador; ubicación del nodo y casas pendiente. Cualquier variante DC requiere adaptar tensión, aislamiento, controlador y protecciones al generador real.

### Desglose S1 de 1 kW

| Partida | Cantidad | Bajo $M | Alto $M | Base |
|---|---:|---:|---:|---|
{boq}
| **Total +25% contingencia** | | **{M(b['total_low_clp'])}** | **{M(b['total_high_clp'])}** | |

Un sistema localizado junto al arroyo, **sin** alimentador a rotonda ni ramales, se estima en ${M(b['local_only_low_clp'])}–{M(b['local_only_high_clp'])} M. No resuelve casas alejadas. Reducir a 0,5 kW cambia caudal/tubo/equipo, pero no reduce proporcionalmente batería, cableado ni obras.

Importación: {fin['import_budget_basis']} El equipo importado presupuestado es una provisión, no el precio de un kit específico que ya cumpla la curva. Si se elige un fabricante documentado de mayor precio, sustituir esa partida completa y revisar compatibilidad, sin sumar dos generadores. No atribuir rentabilidad a sólo 60 días de uso sin comparar alternativas: pedir cotización solar con batería para la misma demanda es razonable.

## Nuevo acceso para autos hasta la rotonda

Origen solicitado: latitud {road['start_wgs84'][1]:.7f}, longitud {road['start_wgs84'][0]:.7f}; cota terreno {F(road['start_elevation_m'],2)} m. Destino inferido del loteo: latitud {road['rotonda_wgs84'][1]:.7f}, longitud {road['rotonda_wgs84'][0]:.7f}; cota {F(road['end_elevation_m'],2)} m. No se acredita continuidad desde ese inicio hacia un camino público, puente ni acceso legal.

La diferencia de cota de {F(road['elevation_gain_m'],2)} m exige como mínimo teórico {F(road['minimum_length_at_10pct_m'],0)} m para no exceder 10%, aun sin considerar curvas. El trazado propuesto tiene **{F(road['length_plan_m'],1)} m en planta** ({F(road['length_3d_m'],1)} m sobre rasante), con giros suavizados a **R15 m** y rasante limitada al 10% por programación lineal. No se ha diseñado acuerdo vertical: el perfil aún necesita suavizado y revisión de detalle. La pendiente no debe interpretarse como certificado de transitabilidad ni como ruta óptima.

Se propone conceptualmente una vía de baja velocidad 10–15 km/h, calzada de 3,5 m, plataforma de 5 m, apartaderos por definir y base granular de 20 cm compactada. Revisar drenaje lateral, bombeo transversal, alcantarilla en la quebrada ID5 y el inicio junto al arroyo ID1; no se incluye un puente mayor comprobado. Para autos sin 4x4 son decisivos el soporte del suelo, drenajes y estado de la superficie, además de la pendiente. Se recomienda estudiar un objetivo menor de pendiente en el proyecto vial cuando lo permita el terreno.

**Afectación:** {impacts}. Eje dentro del deslinde, con unos 118 m atravesando el interior del lote 03 y plataforma de borde que afecta el lote 05. Se penalizaron interiores, sin prohibirlos. Requiere reserva/servidumbre vial y revisión de la subdivisión. La prioridad de baja pendiente impide asumir que todo pueda ir por los linderos existentes.

Movimiento de tierra longitudinal aproximado: corte {F(road['cut_proxy_m3'],0)} m³, relleno {F(road['fill_proxy_m3'],0)} m³; ajuste vertical máximo {F(road['max_vertical_adjustment_m'],2)} m. Es **proxy de perfil por ancho**, no cubicación de obra: faltan secciones transversales, taludes, roca, muros, compactación/esponjamiento y balance de materiales. Se requieren excavadora y equipos de transporte/compactación; no se promete ejecución manual o sólo con herramientas menores.

### Orden de magnitud del acceso

| Partida | Cantidad | Provisión unitaria CLP | Subtotal $M |
|---|---:|---:|---:|
{rboq}
| **Total +30%** | | | **{M(rb['total_low_clp'])}–{M(rb['total_high_clp'])}** |

Base granular incluye **toda** la plataforma circular de rotonda inferida, de unos 52 m de diámetro, además de calzada: {F(road['granular_volume_m3'],0)} m³. Su ejecución por etapas o una solución anular más pequeña podría reducir costo, pero requiere nuevo diseño y no se descuenta arbitrariamente. Provisiones de $45.000–80.000/m³ de base instalada contemplan logística desconocida y no son ofertas de un contratista. {rb['warning']}

## Método, archivos y verificación

Búsqueda vial A* ponderada sobre DTM remuestreado a 2 m para explorar corredores con rasante discretizada, penalización de laderas y centros de lotes; heurística ponderada 8, por tanto no asegura mínimo global. Se suavizan giros con arcos R15. Luego se muestrea DTM nativo cada ~2 m y se ajusta rasante con programación lineal a ≤10%. La búsqueda admite ±5,5 m y el ajuste final hasta ±6 m; la solución concreta utiliza sólo {F(road['max_vertical_adjustment_m'],2)} m. No se usan caminos del KML en ninguna de esas etapas.

Microhidro: enumeración a intervalos de 10 m sobre arroyos con DTM, pares separados 40–240 m de cauce y Hb18–70 m; evaluación de muestra espacialmente diversa de 90 pares. Se comparan tubo recto o cauce, interior de lotes, longitud 3D, línea piezométrica, caudal necesario y cable estimado. Los puntos no fueron elegidos como máximo salto del arroyo completo.

El visor abre con S1 y acceso nuevo; permite seleccionar tres pares, comparar 0,5/1 kW, ver costos y enlaces, descargar KMZ por sitio y KMZ del acceso, y consultar el potencial amplio original. Datos y descargas incorporados en `index.html`; bibliotecas, fondos Esri/OpenTopo y enlaces requieren Internet. Incluye ortomosaicos reducidos para web. No hay costo de licencia ni de API para el procesamiento o el visor actual; la construcción y sus verificaciones son otra inversión.

Archivos: `outputs/microhidro_tres_sitios.json/.geojson`, `outputs/microhidro_S1.kmz` (también S2/S3), `outputs/camino_propuesto.json/.geojson`, `outputs/acceso_rotonda.kmz`, `outputs/perfil_camino.csv`, `outputs/presupuesto_productos.json`. Figuras de propuesta y perfil a continuación.

![Propuesta espacial](outputs/propuesta_acceso_microhidro.png)

![Perfil conceptual de acceso](outputs/perfil_camino.png)

Reproducción con insumos originales y dependencias de `requirements-lock.txt`:

```powershell
.venv/Scripts/python analyze.py
.venv/Scripts/python fit_rotonda.py
.venv/Scripts/python small_hydro.py
.venv/Scripts/python road_plan.py
.venv/Scripts/python planning_finance.py
.venv/Scripts/python build_viewer.py
.venv/Scripts/python make_report.py
.venv/Scripts/python planning_report.py
.venv/Scripts/python verify_outputs.py
.venv/Scripts/python verify_planning.py
node --check outputs/viewer-scripts.js
```

## Fuentes de precios y comprobación técnica

{sources}
- [EPA EPANET](https://www.epa.gov/water-research/epanet): referencia de método hidráulico; C145 y K3 son supuestos del estudio.
- [DOE: familias de turbina](https://www.energy.gov/cmei/water/types-hydropower-turbines): orientación por salto/caudal; elección final con curva de fabricante.

Antes de invertir: verificar tenencia/acceso exterior, aforo de estiaje y reservas de agua, topografía y niveles reales, seguridad ante crecidas, geotecnia vial y predial, trazado eléctrico hacia casas y situación de permisos/uso del agua aplicable al proyecto concreto. No se ha acreditado factibilidad constructiva, disponibilidad firme de agua ni costo final.
'''
    for name in ('PROPUESTA_ACCESO_MICROHIDRO.md','INFORME_PREFACTIBILIDAD.md'):
        (ROOT/name).write_text(text,encoding='utf8');shutil.copy2(ROOT/name,DIST/name)
    plot(sites,road)
    for name in ('propuesta_acceso_microhidro.png','perfil_camino.png'):shutil.copy2(OUT/name,DIST/name)
    print('Informe revisión 3 y figuras generados.')

def plot(sites,road):
    fig,ax=plt.subplots(figsize=(10,12),layout='constrained');fig.set_facecolor('#f6f6ef');ax.set_facecolor('#e7ece2')
    with rasterio.open(ROOT/'LA_CANTINA_dtm.tif') as dem:
        arr=dem.read(1,out_shape=(dem.height//5,dem.width//5),resampling=Resampling.bilinear);arr=np.ma.masked_where(arr<-9999,arr)
        ax.imshow(arr,extent=[dem.bounds.left,dem.bounds.right,dem.bounds.bottom,dem.bounds.top],cmap='terrain',alpha=.45)
    gpd.read_file(OUT/'deslinde.geojson').to_crs(32718).boundary.plot(ax=ax,color='#173d3b',linewidth=1.4)
    lots=gpd.read_file(OUT/'lotes.geojson').to_crs(32718);lots.boundary.plot(ax=ax,color='white',linewidth=1.4)
    for _,l in lots.iterrows():
        pt=l.geometry.representative_point();ax.text(pt.x,pt.y,l['name'],ha='center',fontsize=10,color='#173d3b')
    streams=gpd.read_file(OUT/'hidrografia.geojson').to_crs(32718)
    streams[streams.tipo=='arroyo'].plot(ax=ax,color='#287cba',linewidth=2)
    streams[streams.tipo=='quebrada'].plot(ax=ax,color='#809492',linewidth=1,linestyle='--')
    rf=gpd.read_file(OUT/'camino_propuesto.geojson').to_crs(32718);rf[rf.geometry.geom_type=='LineString'].plot(ax=ax,color='#713525',linewidth=3,label=f"Acceso conceptual, {road['length_plan_m']:.0f} m")
    sf=gpd.read_file(OUT/'microhidro_tres_sitios.geojson').to_crs(32718)
    for s in sites:
        f=sf[sf.site==s['id']];f[f.geometry.geom_type=='LineString'].plot(ax=ax,color='#e57025',linewidth=4)
        pts=f[f.geometry.geom_type=='Point'];pts.plot(ax=ax,color='#e57025',markersize=40)
        pt=pts.geometry.iloc[0];ax.annotate(s['id']+' · '+s['stream_name'],(pt.x,pt.y),xytext=(15,12),textcoords='offset points',fontsize=10,bbox=dict(facecolor='#f6f6ef',alpha=.9,edgecolor='none'))
    ax.set_xlim(685620,686300);ax.set_ylim(4895490,4896690);ax.set_aspect('equal');ax.ticklabel_format(style='plain',useOffset=False)
    ax.set_title('La Cantina · acceso nuevo y tres pares de microhidro\nCAMINOS originales excluidos · coordenadas UTM 18S',loc='left',fontsize=15,color='#153f3d',pad=15)
    ax.set_xlabel('Este · m');ax.set_ylabel('Norte · m');ax.legend(loc='lower right');fig.savefig(OUT/'propuesta_acceso_microhidro.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,3.8),layout='constrained');fig.set_facecolor('#f6f6ef');ss=np.array([p['distance_m'] for p in road['profile']]);zz=np.array([p['terrain_m'] for p in road['profile']]);dd=np.array([p['design_m'] for p in road['profile']])
    ax.plot(ss,zz,color='#69856d',label='Terreno DTM');ax.plot(ss,dd,color='#cc762e',label='Rasante conceptual ≤10%');ax.fill_between(ss,zz,dd,alpha=.18,color='#cc762e');ax.set(xlabel='Distancia en planta · m',ylabel='Cota · m',title=f"Acceso sur → rotonda · {road['length_plan_m']:.0f} m · no es proyecto constructivo");ax.grid(alpha=.15);ax.legend();fig.savefig(OUT/'perfil_camino.png',dpi=150);plt.close(fig)

if __name__=='__main__':main()
