#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import random
import math

def encontrar_vias(net_file):
    """Lista todas las vías disponibles con validación robusta"""
    try:
        tree = ET.parse(net_file)
    except Exception as e:
        print(f"ERROR: No se pudo leer {net_file}: {e}")
        return []

    vias = []

    for edge in tree.findall('.//edge'):
        edge_id = edge.get('id')
        if not edge_id or edge_id.startswith(':'):  # Excluir intersecciones internas
            continue

        from_node = edge.get('from')
        to_node = edge.get('to')

        # Validación robusta del length
        length_str = edge.get('length')
        if length_str is None:
            # Si no hay length, calcularlo desde el shape del primer lane
            lane = edge.find('lane')
            if lane is not None:
                shape = lane.get('shape', '')
                if shape:
                    try:
                        # Calcular longitud desde coordenadas
                        puntos = []
                        for punto in shape.split():
                            x, y = punto.split(',')
                            puntos.append((float(x), float(y)))

                        length = 0
                        for i in range(len(puntos) - 1):
                            x1, y1 = puntos[i]
                            x2, y2 = puntos[i + 1]
                            length += math.sqrt((x2-x1)**2 + (y2-y1)**2)
                    except:
                        length = 100  # Valor por defecto
                else:
                    length = 100  # Valor por defecto
            else:
                length = 100  # Valor por defecto
        else:
            try:
                length = float(length_str)
            except (ValueError, TypeError):
                length = 100  # Valor por defecto

        vias.append({
            'id': edge_id,
            'from': from_node or 'unknown',
            'to': to_node or 'unknown',
            'length': length
        })

    if not vias:
        print("ADVERTENCIA: No se encontraron vías válidas")
        return []

    return sorted(vias, key=lambda x: x['length'], reverse=True)

def validar_archivo_red(net_file):
    """Valida que el archivo de red sea correcto"""
    try:
        tree = ET.parse(net_file)
        root = tree.getroot()

        print(f"✓ Archivo XML válido: {net_file}")
        print(f"✓ Elemento raíz: {root.tag}")

        # Contar elementos
        edges = len(root.findall('.//edge'))
        junctions = len(root.findall('.//junction'))

        print(f"✓ Edges encontrados: {edges}")
        print(f"✓ Junctions encontrados: {junctions}")

        if edges == 0:
            print("ERROR: No se encontraron edges en el archivo")
            return False

        return True

    except Exception as e:
        print(f"ERROR validando archivo: {e}")
        return False

def generar_rutas_densidad_100_seguro(net_file, via_objetivo):
    """
    Genera rutas con validación completa
    """

    if not validar_archivo_red(net_file):
        return 0

    # Configuración para 100 veh/hora
    vehiculos_por_hora = 100
    intervalo_base = 3600 / vehiculos_por_hora  # 36 segundos
    simulation_time = 3600  # 1 hora

    print(f"\nConfigurando densidad de {vehiculos_por_hora} veh/hora")
    print(f"Intervalo base: {intervalo_base:.1f} segundos")

    # Verificar que la vía existe
    tree = ET.parse(net_file)
    edge_encontrado = None

    for edge in tree.findall('.//edge'):
        if edge.get('id') == via_objetivo:
            edge_encontrado = edge
            break

    if edge_encontrado is None:
        print(f"ERROR: Vía '{via_objetivo}' no encontrada!")
        print("Vías disponibles:")
        vias = encontrar_vias(net_file)
        for via in vias[:5]:
            print(f"  - {via['id']}")
        return 0

    # Obtener información de la vía
    length_str = edge_encontrado.get('length')
    if length_str:
        try:
            length = float(length_str)
        except:
            length = 200  # Default
    else:
        length = 200  # Default

    print(f"✓ Vía seleccionada: {via_objetivo} (~{length:.1f}m)")

    # Generar archivo de rutas XML
    rutas_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<routes>
    <!-- Tipo de vehículo MANET optimizado -->
    <vType id="manet_vehicle" accel="2.0" decel="4.0" sigma="0.3"
          length="4.5" width="1.8" maxSpeed="13.89" speedFactor="0.9"/>

'''

    # Generar vehículos
    tiempo_actual = 0
    vehicle_id = 0

    while tiempo_actual < simulation_time:
        # Vehículo principal
        rutas_xml += f'''    <vehicle id="vehicle_{vehicle_id:04d}" type="manet_vehicle" depart="{tiempo_actual:.2f}">
        <route edges="{via_objetivo}"/>
    </vehicle>
'''
        vehicle_id += 1

        # Siguiente vehículo con variación
        variacion = random.uniform(0.7, 1.3)
        tiempo_actual += intervalo_base * variacion

        # Ocasional vehículo en dirección opuesta
        if random.random() < 0.1 and tiempo_actual < simulation_time:
            via_opuesta = f"-{via_objetivo}" if not via_objetivo.startswith('-') else via_objetivo[1:]
            rutas_xml += f'''    <vehicle id="vehicle_{vehicle_id:04d}" type="manet_vehicle" depart="{tiempo_actual:.2f}">
        <route edges="{via_opuesta}"/>
    </vehicle>
'''
            vehicle_id += 1

    rutas_xml += '</routes>'

    # Guardar archivo
    output_file = 'rutas_densidad_100_seguro.rou.xml'
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(rutas_xml)
        print(f"✓ Generados {vehicle_id} vehículos")
        print(f"✓ Archivo guardado: {output_file}")
        return vehicle_id
    except Exception as e:
        print(f"ERROR guardando archivo: {e}")
        return 0

def convertir_a_ns3_seguro(net_file, rutas_file):
    """
    Conversión a NS-3 con manejo robusto de errores
    """

    try:
        net_tree = ET.parse(net_file)
        rutas_tree = ET.parse(rutas_file)
    except Exception as e:
        print(f"ERROR leyendo archivos: {e}")
        return []

    # Extraer geometría con validación
    edges_geometry = {}

    for edge in net_tree.findall('.//edge'):
        edge_id = edge.get('id')
        if not edge_id:
            continue

        lane = edge.find('lane')
        if lane is None:
            continue

        shape = lane.get('shape')
        if not shape:
            continue

        try:
            puntos = []
            for punto in shape.split():
                if ',' in punto:
                    x_str, y_str = punto.split(',')
                    x = float(x_str)
                    y = float(y_str)
                    puntos.append((x, y))

            if len(puntos) >= 2:  # Solo guardar si tiene al menos 2 puntos
                edges_geometry[edge_id] = puntos

        except (ValueError, IndexError) as e:
            print(f"ADVERTENCIA: Problema procesando shape de {edge_id}: {e}")
            continue

    print(f"✓ Procesadas {len(edges_geometry)} geometrías de vías")

    # Procesar vehículos
    vehiculos_ns3 = []

    for vehicle in rutas_tree.findall('.//vehicle'):
        vehicle_id = vehicle.get('id')
        if not vehicle_id:
            continue

        depart_str = vehicle.get('depart')
        if not depart_str:
            continue

        try:
            depart_time = float(depart_str)
        except (ValueError, TypeError):
            print(f"ADVERTENCIA: Tiempo de salida inválido para {vehicle_id}")
            continue

        route = vehicle.find('route')
        if route is None:
            continue

        edges_str = route.get('edges')
        if not edges_str:
            continue

        edges = edges_str.split()

        # Generar waypoints
        waypoints = []
        tiempo_actual = depart_time

        for edge_id in edges:
            if edge_id not in edges_geometry:
                continue

            puntos_edge = edges_geometry[edge_id]

            # Crear waypoints cada cierta distancia
            num_waypoints = max(2, min(10, len(puntos_edge)))

            for i in range(num_waypoints):
                if i < len(puntos_edge):
                    x, y = puntos_edge[i]
                else:
                    # Interpolar
                    ratio = i / (num_waypoints - 1)
                    x1, y1 = puntos_edge[0]
                    x2, y2 = puntos_edge[-1]
                    x = x1 + (x2 - x1) * ratio
                    y = y1 + (y2 - y1) * ratio

                # Pequeña variación aleatoria
                x += random.uniform(-2, 2)
                y += random.uniform(-2, 2)

                velocidad = random.uniform(7, 11)  # m/s

                waypoints.append({
                    'time': round(tiempo_actual, 2),
                    'x': round(x, 2),
                    'y': round(y, 2),
                    'speed': round(velocidad, 2)
                })

                tiempo_actual += random.uniform(8, 20)

        if len(waypoints) >= 2:  # Solo agregar si tiene suficientes waypoints
            vehiculos_ns3.append({
                'id': vehicle_id,
                'waypoints': waypoints
            })

    print(f"✓ Procesados {len(vehiculos_ns3)} vehículos válidos para NS-3")
    return vehiculos_ns3

def generar_archivo_ns3_seguro(vehiculos_data, output_file="manet_density_100_seguro.tcl"):
    """Genera archivo NS-3 con validación"""

    if not vehiculos_data:
        print("ERROR: No hay datos de vehículos para generar archivo NS-3")
        return False

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# NS-3 Mobility File - Density 100 vehicles/hour\n")
            f.write(f"# Total valid nodes: {len(vehiculos_data)}\n\n")

            # Posiciones iniciales
            f.write("# Initial positions\n")
            for vehiculo in vehiculos_data:
                if vehiculo['waypoints']:
                    wp_inicial = vehiculos_data[0]['waypoints'][0]
                    node_id = vehiculo['id'].replace('vehicle_', '')

                    f.write(f"$node_({node_id}) set X_ {wp_inicial['x']}\n")
                    f.write(f"$node_({node_id}) set Y_ {wp_inicial['y']}\n")
                    f.write(f"$node_({node_id}) set Z_ 1.5\n")

            f.write("\n# Movement commands\n")

            # Comandos de movimiento
            for vehiculo in vehiculos_data:
                node_id = vehiculo['id'].replace('vehicle_', '')

                for wp in vehiculo['waypoints'][1:]:
                    f.write(f"$ns_ at {wp['time']:.2f} "
                           f"\"$node_({node_id}) setdest "
                           f"{wp['x']} {wp['y']} {wp['speed']}\"\n")

        print(f"✓ Archivo NS-3 generado exitosamente: {output_file}")
        return True

    except Exception as e:
        print(f"ERROR generando archivo NS-3: {e}")
        return False

def main():
    """Función principal con manejo de errores completo"""

    net_file = 'la_calera_map_v3.net.xml'

    print("=== GENERADOR MANET DENSIDAD 100 (VERSIÓN SEGURA) ===\n")

    # Verificar que el archivo existe
    try:
        with open(net_file, 'r') as f:
            pass
    except FileNotFoundError:
        print(f"ERROR: Archivo {net_file} no encontrado!")
        print("Asegúrate de que el archivo esté en el directorio actual.")
        return

    # 1. Analizar vías
    print("1. Analizando vías disponibles...")
    vias = encontrar_vias(net_file)

    if not vias:
        print("ERROR: No se encontraron vías válidas")
        return

    print(f"✓ Encontradas {len(vias)} vías")
    print(f"Top 5 vías más largas:")
    for i, via in enumerate(vias[:5]):
        print(f"  {i}: {via['id']} - {via['length']:.1f}m")

    # 2. Seleccionar vía
    via_seleccionada = vias[0]['id']
    print(f"\n2. Usando vía: {via_seleccionada}")

    # 3. Generar rutas
    print(f"\n3. Generando rutas...")
    num_vehiculos = generar_rutas_densidad_100_seguro(net_file, via_seleccionada)

    if num_vehiculos == 0:
        print("ERROR: No se pudieron generar rutas")
        return

    # 4. Convertir a NS-3
    print(f"\n4. Convirtiendo a NS-3...")
    vehiculos_ns3 = convertir_a_ns3_seguro(net_file, 'rutas_densidad_100_seguro.rou.xml')

    if not vehiculos_ns3:
        print("ERROR: No se pudieron procesar vehículos para NS-3")
        return

    # 5. Generar archivo final
    print(f"\n5. Generando archivo final...")
    if generar_archivo_ns3_seguro(vehiculos_ns3):
        print(f"\n=== ÉXITO ===")
        print(f"Archivos generados:")
        print(f"  - rutas_densidad_100_seguro.rou.xml (SUMO)")
        print(f"  - manet_density_100_seguro.tcl (NS-3)")
        print(f"  - {len(vehiculos_ns3)} nodos válidos")
        print(f"✓ Listo para usar en NS-3!")
    else:
        print("ERROR en la generación final")

if __name__ == "__main__":
    main()
