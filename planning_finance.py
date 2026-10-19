"""Presupuesto paramétrico trazable; no es cotización ni proyecto eléctrico."""
from pathlib import Path
import json, math
ROOT=Path(__file__).parent; OUT=ROOT/'outputs'

PRODUCTS=[
 dict(name='AliExpress · generador 1/2 kW',url='https://www.aliexpress.com/item/1005012619584537.html',reference='https://ms.pricearchive.org/aliexpress.com/item/1005012619584537',price='US$709,80 archivados el 16-09-2026',verdict='Preselección condicionada: no se verificó curva H/Q ni variante; no comprar aún.'),
 dict(name='AliExpress · compacto 300/500/1000 W',url='https://www.aliexpress.com/item/1005008506351365.html',reference='https://sv.pricearchive.org/aliexpress.com/item/1005008506351365',price='Sin precio comprobado',verdict='Pedir curva para H neto 24,3 m y Q 6,46 L/s; confirmar equipo completo y regulación.'),
 dict(name='AliExpress · axial 1 kW',url='https://www.aliexpress.com/item/1005012367548289.html',reference='https://www.pricearchive.org/aliexpress.com/item/1005012367548289',price='US$478,62 archivados el 21-09-2026',verdict='Descartado como selección automática: no se acredita compatibilidad con 20–26 m de salto.'),
 dict(name='AliExpress · rodete Pelton suelto',url='https://www.aliexpress.com/item/1005009309567283.html',reference='https://vi.pricearchive.org/aliexpress.com/item/1005009309567283',price='US$67,32 históricos; sólo rodete',verdict='No es un sistema generador completo. No usar ese precio como costo del proyecto.'),
 dict(name='PowerSpout PLT · referencia técnica',url='https://www.powerspout.com/products/powerspout-plt',reference='https://www.powerspout.com/products/powerspout-plt',price='NZD 3.773,70, sin GST, flete ni importación',verdict='Pelton comercial de referencia, 1.200 W estándar. Pedir configuración y curva para el punto calculado; no garantiza 1 kW sólo por su placa.')
]
SOURCES=[
 dict(item='HDPE PE100 PN16',url='https://s2l.cl/collections/tuberias-hdpe',observed='90 mm x 6 m: $43.690; 110 mm x 6 m: $64.960; confirmar IVA y despacho.'),
 dict(item='Cable RV-K 3x10 mm², no AWG',url='https://rhona.cl/producto/137/cable-rv-k-3x10mm2.html',observed='$4.265/m IVA incluido; sin stock web. Referencia, no disponibilidad.'),
 dict(item='Batería BESS 51,2 V 100 Ah',url='https://www.solartex.cl/tienda/producto/bateria-de-litio-bessenergy-512v-100ah/',observed='$763.000 + IVA = $907.970; 5,12 kWh nominales.'),
 dict(item='Inversor Epever 3 kW 48 V',url='https://sunstorm.cl/productos/inversor-off-grid-3000w-48v-onda-sinusoidal-pura-epever',observed='$422.990 IVA incluido; el cargador/regulador hidro se presupuesta aparte.'),
 dict(item='Base granular: referencia de modelo',url='https://chile.generadordeprecios.info/espacios_urbanos/Firmes_y_pisos_urbanos/Bases_y_subbases/Granulares/Base_granular_0_0_4_3.html',observed='$23.577,94/m³ en modelo CYPE; no es precio entregado en el predio. Se adopta provisión mayor por logística.'),
 dict(item='Importación: referencia general',url='https://www.sii.cl/aprenda_sobre_impuestos/impuestos/impuestos_indirectos.htm',observed='IVA y derechos dependen del régimen y origen; usar cotización de costo puesto en Chile, no precio de pantalla.')
]

def main():
    small=json.loads((OUT/'microhidro_tres_sitios.json').read_text(encoding='utf8'))
    budgets={}
    for s in small['sites']:
        plan=s['plans'][1]; length=s['cable_length_allowance_m']
        # Comprobación resistiva orientativa a 230 V monofásico, 1 kW y FP=1.
        # No dimensiona ampacidad, arranque, protecciones ni ramales de casas.
        section=10 if 2*.0225*length*1000/(230**2*10)<=.05 else 16
        drop=2*.0225*length*1000/(230**2*section)*100
        pipe_unit=43690/6 if plan['pipe_od_mm']==90 else 64960/6
        purchase=math.ceil(s['length_m']*1.10/6)*6
        items=[
          ('Turbina + generador económico importado, puesto en Chile',1,1200000,2000000,'Provisión; referencia Ali histórica, curva y flete sin confirmar'),
          ('Regulación hidro, carga de desvío y cargador compatible',1,600000,1200000,'Provisión; no duplicar si el kit los incluye'),
          ('HDPE PN16 SDR11, m comprados',purchase,pipe_unit*1.19,pipe_unit*1.5,'Precio publicado elevado 19% conservador; confirmar tratamiento de IVA'),
          ('Válvulas, uniones, anclajes y venteo',1,250000,500000,'Provisión'),
          ('Rejilla, desarenado y caseta pequeña en margen segura',1,800000,1600000,'Obra liviana condicionada a terreno y crecidas'),
          (f'Alimentador hasta rotonda, Cu {section} mm², m estimados',length,4265 if section==10 else 7000,8000 if section==10 else 12000,'10 mm²: referencia RHONA sin stock; 16 mm²: provisión propia'),
          ('Ducto/soportes y tendido del alimentador, m estimados',length,1500,4000,'Provisión; roca, puente o tendido aéreo especial no cubicados'),
          ('Batería LiFePO4 5,12 kWh nominal',1,907970,1200000,'Referencia comercial + IVA; compatibilidad BMS por confirmar'),
          ('Inversor senoidal 48 V, 3 kW compartidos',1,422990,700000,'Cargador hidro aparte; no son 3 kW por casa'),
          ('Tablero, tierra, sobretensión y protecciones',1,400000,800000,'Provisión'),
          ('Ramales básicos a 2–3 casas',1,600000,1400000,'Provisión no cubicada; casas aún no localizadas'),
          ('Montaje, traslados y puesta en marcha',1,800000,1600000,'Provisión sin apertura de camino'),
          ('Levantamiento de detalle, aforo y revisión eléctrica',1,400000,900000,'Provisión de contratación; cálculo SIG realizado con herramientas gratuitas')]
        rows=[dict(item=n,quantity=q,unit_low_clp=a,unit_high_clp=b,low_clp=q*a,high_clp=q*b,basis=basis) for n,q,a,b,basis in items]
        low=sum(x['low_clp'] for x in rows);high=sum(x['high_clp'] for x in rows)
        local=[x for x in rows if not any(t in x['item'] for t in ('Alimentador','Ducto/soportes','Ramales'))]
        budgets[s['id']]=dict(items=rows,subtotal_low_clp=low,subtotal_high_clp=high,contingency_pct=25,total_low_clp=low*1.25,total_high_clp=high*1.25,
            local_only_low_clp=sum(x['low_clp'] for x in local)*1.25,local_only_high_clp=sum(x['high_clp'] for x in local)*1.25,
            cable_section_mm2=section,cable_voltage_drop_pct=drop,cable_basis='230 V AC, 1 kW, FP1, cobre caliente rho=0,0225 Ω mm²/m; sólo aproximación resistiva.',
            excluded='Sin apertura de camino, compra de tierra/servidumbres, derechos o permisos específicos, extensión a casas distantes ni obra mayor en roca/cauce. Costos de trámites por determinar.')
    roadfile=OUT/'camino_propuesto.json';roadbudget=None
    if roadfile.exists():
        road=json.loads(roadfile.read_text(encoding='utf8'));L=road['length_plan_m'];earth=road['cut_proxy_m3']+road['fill_proxy_m3']
        items=[('Base granular 20 cm, calzada + rotonda',road['granular_volume_m3'],45000,80000),('Movimiento longitudinal de tierras, proxy',earth,15000,30000),('Despeje y preparación de plataforma',L,5000,10000),('Drenajes, alcantarillas y cunetas: provisión',1,4000000,10000000),('Movilización, topografía y diseño de detalle',1,3000000,7000000)]
        rows=[dict(item=n,quantity=q,unit_low_clp=a,unit_high_clp=b,low_clp=q*a,high_clp=q*b) for n,q,a,b in items]
        roadbudget=dict(items=rows,total_low_clp=sum(x['low_clp'] for x in rows)*1.30,total_high_clp=sum(x['high_clp'] for x in rows)*1.30,contingency_pct=30,
            warning='Orden de magnitud, no oferta. Tierra es proxy longitudinal; faltan perfiles transversales, taludes, roca, muros, puentes y disposición de excedentes. No es límite superior de costo. Rotonda completa incluida; radio inferido del loteo, tamaño por revisar.')
    result=dict(date='2026-10-19',currency='CLP',status='Estimación de orden de magnitud con provisiones; no cotización',budgets=budgets,road=roadbudget,products=PRODUCTS,sources=SOURCES,
                aliexpress_status='Acceso automatizado directo bloqueado. Enlaces identificados mediante referencias públicas previamente consultadas; precios históricos, variante, stock, flete y curva no verificados.',
                import_budget_basis='US$1 = $1.000 CLP es supuesto presupuestario, no tipo de cambio vigente. Ejemplo US$700 + US$200 flete: $900.000 CIF; impuestos, gestión y flete interior incluidos mediante provisión global. Confirmar régimen aplicable con cotización puesta en Chile.',
                recommendation='S1 · Pelton compacta 1 kW, batería 5,12 kWh e inversor 3 kW compartidos, condicionada a aforo de verano y acceso exterior. Comparar cotización solar por uso de sólo 60 días.')
    (OUT/'presupuesto_productos.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print({k:(round(v['total_low_clp']),round(v['total_high_clp'])) for k,v in budgets.items()});print('Camino',roadbudget and (round(roadbudget['total_low_clp']),round(roadbudget['total_high_clp'])))

if __name__=='__main__':main()
