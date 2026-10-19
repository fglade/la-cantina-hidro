# La Cantina · acceso y microhidro de verano

**[Visor público](https://la-cantina-hidro.craftysmile14.chatgpt.site)** · [Informe y presupuesto](PROPUESTA_ACCESO_MICROHIDRO.md) · [KMZ S1](outputs/microhidro_S1.kmz) · [KMZ del acceso nuevo](outputs/acceso_rotonda.kmz)

Revisión 3 · 19-10-2026. Propuesta para **2–3 casas de consumo básico durante 60 días de verano**. CAMINOS hipotéticos excluidos de los cálculos y del visor. Se preservan los seis cauces y las 512 curvas completos, incluido el arroyo norte exterior al deslinde. Quebradas no permanentes: última prioridad.

![Propuesta espacial](outputs/propuesta_acceso_microhidro.png)

## Sistema pequeño

Recomendación condicionada a aforo: **1 kW continuo**, batería nominal 5,12 kWh e inversor de **3 kW compartidos**. Demanda supuesta de tres casas: 4,5–9 kWh/día. Con disponibilidad 80% y entrega 90% supuestas: 17,28 kWh útiles/día y 1.037 kWh/60 días. Sin calefacción, termo ni cocina eléctrica. No es pronóstico de verano; faltan caudal y consumos reales.

| Par | Cauce | Hb | Tubo 3D | Q para 1 kW | H neto | HDPE exterior PN16 |
|---|---|---:|---:|---:|---:|---:|
| S1, primera visita | Norte | 26,14 m | 48,75 m | 6,46 L/s | 24,29 m | 90 mm |
| S2, alternativa | Norte | 19,69 m | 54,0 m | 8,54 L/s | 18,37 m | 110 mm |
| S3, comparación | Límite sur | 21,64 m | 46,8 m | 7,58 L/s | 20,70 m | 110 mm |

**Los tres pares quedan fuera del deslinde original**; acceso y tenencia no acreditados. Cotas de terreno DTM, no niveles de agua. Ranking por tubos cortos y cable estimado, sin garantía de mínimo global ni facilidad constructiva.

Presupuesto S1: **$12,0–22,8 millones CLP**, con equipo importado como provisión, batería, regulación, obras pequeñas, montaje y unos 477 m de alimentador estimado hasta rotonda; incluye 25% contingencia. Sin camino, servidumbres ni tasas específicas. Ubicaciones de casas y trazado eléctrico pendientes. Pelton compacta de 1 kW a Hn24,3 m/Q6,46 L/s, confirmada con curva de fabricante.

AliExpress bloqueó el acceso automatizado directo. El visor e informe incluyen enlaces identificados con referencias públicas previas y precios históricos. **Variante, curva H/Q, stock, precio actual y flete no verificados: no hay un anuncio confirmado para comprar.** PowerSpout PLT se usa como referencia técnica documentada, con precio de fabricante separado del costo instalado. Por uso de sólo dos meses, comparar una cotización solar con batería antes de invertir.

## Acceso nuevo

Desde la desembocadura occidental del arroyo sur ID1: **660 m en planta**, subida 61,16 m, rasante calculada ≤10% y curvas R15. Calzada conceptual 3,5 m, plataforma 5 m, granular 20 cm. Eje dentro del deslinde; atraviesa unos 118 m del lote 03. Rotonda inferida de arcos de linderos de lotes, sin CAMINOS.

**Requiere maquinaria**, cortes/rellenos hasta 3,86 m, drenajes, revisión geotécnica y proyecto vial. No es camino existente ni certificado para autos sin 4x4. Orden de magnitud **$116,6–225,6 millones CLP**, incluyendo plataforma completa de rotonda inferida y 30% contingencia. No es oferta ni límite superior. Tierra como proxy longitudinal; faltan perfiles transversales, taludes, roca, muros y posibles obras mayores.

![Perfil del acceso](outputs/perfil_camino.png)

## Archivos

| Archivo | Uso |
|---|---|
| index.html | Folium, datos, imágenes y descargas incorporados. Internet para bibliotecas y fondos. |
| PROPUESTA_ACCESO_MICROHIDRO.md | Informe principal, coordenadas, hidráulica, costos y fuentes. |
| APENDICE_POTENCIAL.md | Potencial amplio original 10/25/50/100 L/s sin preferencia por CAMINOS. |
| small_hydro.py | Tres pares cortos y planes 0,5/1 kW. |
| fit_rotonda.py | Ajuste de rotonda sólo con lotes. |
| road_plan.py | Búsqueda ponderada, curvas y rasante conceptual. |
| planning_finance.py | Presupuesto paramétrico y referencias de productos. |
| build_viewer.py, planning_map.py, planning_panel.html | Visor revisión 3 y KMZ. |
| analyze.py, hydraulics.py | Análisis SIG y potencial amplio. |
| verify_outputs.py, verify_planning.py | Verificaciones de vectores, balances, geometría, costos y exportación. |
| planning_report.py, make_report.py | Informes, figuras y paquete del estudio. |

Python 3.12 y dependencias de requirements-lock.txt. Los TIF voluminosos no están en GitHub y se necesitan para recalcular; conservar nombres de insumos originales y sidecars SHP.

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-lock.txt
.venv/Scripts/python analyze.py
.venv/Scripts/python fit_rotonda.py
.venv/Scripts/python small_hydro.py
.venv/Scripts/python road_plan.py
.venv/Scripts/python planning_finance.py
.venv/Scripts/python build_viewer.py
.venv/Scripts/python planning_report.py
.venv/Scripts/python make_report.py
.venv/Scripts/python verify_outputs.py
.venv/Scripts/python verify_planning.py
node --check outputs/viewer-scripts.js
```

DTM: cobertura aproximada de 50,6% del deslinde, usando además su topografía exterior. ID6 visible sin potencia por falta de DTM. Software gratuito no sustituye aforo de estiaje, proyecto constructivo, revisión eléctrica ni acceso/uso del agua acreditado. Publicación pública autorizada por el propietario.
