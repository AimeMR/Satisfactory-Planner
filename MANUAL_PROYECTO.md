# SATISFACTORY PLANNER — Manual del Proyecto

## Índice

1. [Descripción General](#descripción-general)
2. [Requisitos e Instalación](#requisitos-e-instalación)
3. [Arquitectura del Proyecto](#arquitectura-del-proyecto)
4. [Base de Datos](#base-de-datos)
5. [Motor de Producción](#motor-de-producción)
6. [Interfaz Gráfica](#interfaz-gráfica)
7. [Guía de Uso](#guía-de-uso)
8. [Exportar e Importar Proyectos](#exportar-e-importar-proyectos)
9. [Internacionalización](#internacionalización)
10. [Registro de Logs](#registro-de-logs)
11. [Preguntas Frecuentes](#preguntas-frecuentes)

---

## Descripción General

**Satisfactory Planner** es una aplicación de escritorio desarrollada en **Python 3.10+** con **PySide6 (Qt 6)** para planificar cadenas de producción del videojuego *Satisfactory*.

> **🚀 EVOLUCIÓN DEL PROYECTO:** Este manual documenta la fase "base" del planificador interactivo. A partir de esta fundación, el proyecto se transformará en una herramienta automática: **la aplicación preguntará al usuario qué material desea producir y generará, conectará y optimizará automáticamente toda la línea de máquinas necesaria.**

Permite al usuario:
- Colocar máquinas en un lienzo infinito con zoom y paneo.
- Seleccionar recetas para cada máquina.
- Conectar salidas con entradas arrastrando puertos.
- Visualizar tasas de producción, consumo y déficits/excedentes en tiempo real.
- Organizar máquinas en grupos (sub-fábricas) colapsables.
- Gestionar **múltiples bases de datos** aislando diferentes configuraciones (e.g., base, con mods).
- Añadir **Materiales, Máquinas y Recetas personalizadas** mediante cuadros de diálogo integrados.
- Gestionar múltiples proyectos independientes delegados a su respectiva base de datos.
- Exportar e importar proyectos como archivos JSON.
- Cambiar entre Inglés y Español con un solo clic.

---

## Requisitos e Instalación

### Requisitos del Sistema
- **Python** 3.10 o superior
- **Sistema operativo**: Windows, macOS o Linux

### Dependencias
El proyecto solo requiere una dependencia externa:

```
PySide6
```

### Instalación Paso a Paso

```bash
# 1. Clonar o descargar el repositorio
git clone <url-del-repositorio>
cd Satisfactory-Planner

# 2. Crear un entorno virtual (recomendado)
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar la aplicación
python main.py
```

La base de datos SQLite por defecto (`satisfactory.db`) se crea automáticamente en la primera ejecución dentro de la carpeta `databases/` con todos los materiales, máquinas y recetas de los Niveles 1 al 8 precargados.

---

## Arquitectura del Proyecto

```
Satisfactory-Planner/
│
├── main.py                  # Punto de entrada — inicializa DB, Qt y ventana principal
│
├── database/                # Capa de datos
│   ├── __init__.py
│   ├── db.py               # Gestión de DBs múltiples, SQLite, esquema y migraciones
│   ├── crud.py             # Operaciones CRUD para todas las tablas
│   ├── seed_data.py        # Datos base del juego (materiales, máquinas, recetas)
│   └── io.py               # Exportar/importar proyectos como JSON
│
├── databases/               # Almacenamiento local de archivos .db
│
├── engine/                  # Motor de cálculo
│   ├── __init__.py
│   └── graph.py            # Grafo de producción y cálculos de flujo
│
├── ui/                      # Interfaz gráfica (PySide6)
│   ├── __init__.py
│   ├── main_window.py      # Ventana principal, barra lateral, barra de herramientas
│   ├── canvas.py           # Escena y vista del lienzo infinito
│   ├── machine_node.py     # Nodo visual de máquina (QGraphicsItem)
│   ├── connection_line.py  # Línea de conexión Bézier entre puertos
│   ├── port_item.py        # Puertos de entrada/salida en los nodos
│   ├── sub_factory_node.py # Grupos de máquinas (sub-fábricas)
│   ├── settings_cache.py   # Caché de ajustes para rendimiento en paint()
│   └── i18n.py             # Cadenas de texto en Inglés/Español
│
├── satisfactory.db          # Base de datos SQLite (generada automáticamente)
├── error.log                # Registro de errores y eventos
├── requirements.txt         # Dependencias (PySide6)
└── .gitignore               # Archivos excluidos de Git
```

### Flujo de Datos

```
main.py → initialize_db() + seed_db()
        → QApplication + MainWindow
                ↓
        MainWindow._load_layout()
                ↓
        Lee Placed_Nodes + Connections + Groups de la DB
                ↓
        Crea MachineNode, ConnectionLine, SubFactoryNode en la FactoryScene
                ↓
        FactoryScene.recalculate()
                ↓
        engine/graph.py → build_graph() + calculate_production()
                ↓
        NodeResult + ConnectionResult → se aplican a cada nodo/línea visual
```

---

## Base de Datos

### Esquema (SQLite)

| Tabla | Descripción |
|-------|-------------|
| **Materials** | Todos los materiales del juego (nombre, tipo: solid/liquid/gas) |
| **Machines** | Tipos de máquina (nombre, categoría, potencia base, puertos E/S) |
| **Recipes** | Recetas disponibles por máquina (nombre, tiempo de fabricación) |
| **Recipe_Materials** | Ingredientes de cada receta (material, cantidad, es_entrada) |
| **Projects** | Proyectos del usuario (nombre, fecha de modificación) |
| **Groups** | Grupos de máquinas — sub-fábricas (posición, estado colapsado) |
| **Placed_Nodes** | Instancias de máquinas colocadas en el lienzo (posición, receta, velocidad) |
| **Connections** | Conexiones entre puertos de nodos (origen, destino, material, velocidad) |
| **Settings** | Preferencias clave/valor (idioma, estilo de línea, visibilidad) |

### Migraciones

El esquema se gestiona con **versionado incremental**:
- La versión actual se almacena en `Settings` como `schema_version`.
- Todas las tablas usan `CREATE TABLE IF NOT EXISTS` para idempotencia.
- Las migraciones futuras se aplican secuencialmente (por ejemplo: `if version < 4: ALTER TABLE ...`).
- **Nunca se borran datos del usuario** durante migraciones.

### Datos Semilla

Al iniciar por primera vez, `seed_data.py` inserta:
- **~75 materiales** (minerales, lingotes, piezas, líquidos, gases)
- **19 máquinas** (extractores, producción, logística, energía)
- **~60 recetas** (fundición, construcción, ensamblaje, refinado, nuclear)

El versionado de semilla se controla con la clave `seed_version` en `Settings`, evitando reinsertar datos innecesariamente.

### Operaciones CRUD

El módulo `crud.py` proporciona funciones para cada tabla:

```python
# Materiales
get_all_materials() → list[dict]
get_material_by_id(id) → dict | None
add_material(name, type) → int

# Máquinas
get_all_machines() → list[dict]
add_machine(name, category, power, inputs, outputs) → int

# Recetas
get_all_recipes() → list[dict]          # Incluye materiales de cada receta
get_recipes_for_machine(machine_id) → list[dict]

# Nodos Colocados
get_all_placed_nodes(project_id) → list[dict]
add_placed_node(project_id, machine_id, ...) → int
update_placed_node(node_id, **kwargs) → None
delete_placed_node(node_id) → None

# Conexiones
get_all_connections(project_id) → list[dict]
add_connection(source_id, target_id, ...) → int
delete_connection(connection_id) → None

# Proyectos
get_all_projects() → list[dict]
add_project(name) → int
rename_project(project_id, new_name) → None
delete_project(project_id) → None       # Cascada: borra nodos y conexiones

# Grupos
get_all_groups(project_id) → list[dict]
add_group(project_id, name, x, y) → int
delete_group(group_id) → None

# Configuración
get_setting(key, default) → str | None
set_setting(key, value) → None
```

---

## Motor de Producción

El módulo `engine/graph.py` calcula las tasas de producción de toda la cadena.

### Algoritmo

1. **Construir el grafo**: `build_graph()` convierte los nodos y conexiones de la DB en una estructura de adyacencia.

2. **Calcular producción por nodo**: Para cada nodo con receta asignada:
   ```
   tasa = (cantidad / tiempo_fabricación) × 60 × velocidad_reloj
   ```

3. **Propagar flujo por logística**: Los Mergers y Splitters no tienen receta; acumulan el flujo de entrada y lo dividen entre sus salidas. Se realizan hasta 5 pasadas de propagación.

4. **Evaluar estado de conexiones**:
   - ✅ **OK**: Suministro = Demanda
   - ⚠️ **Déficit**: Suministro < Demanda (línea naranja punteada)
   - ℹ️ **Excedente**: Suministro > Demanda (línea azul)
   - ❌ **Material incompatible**: La salida no coincide con la entrada (línea roja)

### Fórmula de Energía

```
Potencia (MW) = Potencia_base × velocidad_reloj ^ 1.321
```

Esta es la fórmula oficial de overclock de Satisfactory.

---

## Interfaz Gráfica

### Componentes Principales

| Componente | Archivo | Descripción |
|-----------|---------|-------------|
| **MainWindow** | `main_window.py` | Ventana raíz con barra lateral dinámica, barra de herramientas principal compactada y canvas |
| **FactoryScene** | `canvas.py` | Escena de Qt que contiene todos los nodos y conexiones |
| **FactoryView** | `canvas.py` | Vista con cuadrícula de puntos, zoom (scroll) y paneo (botón central/derecho) |
| **MachineNode** | `machine_node.py` | Nodo visual de máquina con combo de recetas y puertos |
| **ConnectionLine** | `connection_line.py` | Curva Bézier entre puertos con etiqueta de flujo |
| **PortItem** | `port_item.py` | Círculo de puerto (azul=entrada, naranja=salida) |
| **SubFactoryNode** | `sub_factory_node.py` | Contenedor visual para grupos colapsables |
| **ConnectionLabel** | `connection_line.py` | Etiqueta flotante sobre las conexiones |
| **Add Element Dialogs**| `add_element_dialog.py` | Asistente de ventanas secuenciales para la creación custom de Material/Máquina/Receta |

### Paleta de Colores

La aplicación usa un tema oscuro inspirado en Satisfactory:

| Elemento | Color | Hex |
|----------|-------|-----|
| Fondo | Azul marino profundo | `#1a1a2e` |
| Barra lateral | Azul oscuro | `#16213e` |
| Acento | Rojo rosado | `#e94560` |
| Texto | Gris claro | `#eaeaea` |
| Cuadrícula | Púrpura tenue | `#44446a` |

### Colores por Máquina

Cada tipo de máquina tiene un color distintivo:
- **Fundidores/Fundiciones**: Tonos cobre/marrón
- **Constructores**: Verde oscuro
- **Ensambladores**: Azul oscuro
- **Fabricantes**: Púrpura
- **Refinerías**: Ámbar
- **Splitter**: Naranja vibrante (`#ff6d00`)
- **Merger**: Cian vibrante (`#00e5ff`)

### Colores de Conexión (por estado)

| Estado | Color | Significado |
|--------|-------|-------------|
| OK (con flujo) | 🟢 Verde `#4caf50` | Producción equilibrada |
| Déficit | 🟠 Naranja `#ff9800` | Suministro insuficiente |
| Excedente | 🔵 Azul `#2196f3` | Producción excesiva |
| Material incompatible | 🔴 Rojo `#ff1744` | Material incorrecto |
| Inactivo | ⚫ Gris `#555577` | Sin flujo |

---

## Guía de Uso

### Colocar una Máquina
1. En la **barra lateral izquierda**, encuentra la máquina deseada por categoría.
2. **Doble clic** en el nombre de la máquina.
3. La máquina aparece en el centro de la vista actual.

### Seleccionar Receta
1. Clic en el **combo de receta** dentro del nodo de máquina.
2. Selecciona la receta deseada del menú desplegable.
3. Las tasas de producción se recalculan automáticamente.

### Conectar Máquinas
1. Clic y arrastra desde un **puerto de salida** (naranja, borde derecho).
2. Suelta sobre un **puerto de entrada** (azul, borde izquierdo) de otra máquina.
3. La conexión se crea con su Bézier y etiqueta de flujo.

### Navegar por el Lienzo
| Acción | Control |
|--------|---------|
| Paneo | Botón central del ratón (arrastrar) o botón derecho |
| Zoom | Rueda del ratón |
| Selección rectangular | Clic izquierdo + arrastrar en área vacía |
| Selección múltiple | Click izquierdo sobre cada elemento |

### Eliminar Elementos
- **Tecla Delete/Supr**: Elimina todos los elementos seleccionados.
- **Clic derecho** → "🗑 Delete Machine" o "Delete Connection".

### Ajustar Velocidad de Reloj
1. Clic derecho en un nodo de máquina.
2. Selecciona "🕒 Change Clock Speed".
3. Introduce el multiplicador (0.01 – 2.50).

### Copiar y Pegar
- **Ctrl+C**: Copia los nodos seleccionados y sus conexiones internas.
- **Ctrl+V**: Pega una copia desplazada +32px en ambos ejes.

### Agrupar Máquinas
1. Selecciona 2 o más máquinas.
2. Clic derecho → "📦 Group Selected Nodes".
3. Los nodos se encierran en un grupo con borde punteado.
4. Clic en el botón **+/-** del grupo para expandir/colapsar.

### Alternar / Cerrar Barra Lateral
La aplicación cuenta con una barra lateral colapsable. Se esconde pulsando el botón con la flecha `◀` en el divisor vertical (Splitter). Al esconderse, la barra lateral desaparece, pero la franja fina del botón (`▶`) se mantiene visible para poder volver a acceder rápidamente.

### Añadir Elementos Personalizados
1. En la parte inferior de la barra lateral, pulsa el botón `➕ Add Element`.
2. Escoge entre **Material**, **Machine** o **Recipe**.
3. Rellena los datos en el cuadro de diálogo:
   - Para las recetas, debes indicar el tiempo de crafteo, la máquina operaria, y sus ingredientes correspondientes (es posible eliminar ingredientes pulsando el botón ➖).
4. El nuevo elemento se guardará en tu base de datos actual para todos los proyectos compartidos.

### Bases de Datos y Proyectos
La app permite alternar entre bases de datos enteras desde el combo de la barra superior, ideal cuando se planifica con diferentes modos de juego y dependencias (ej: DB Vainilla vs DB Mods).
Desde la esquina superior izquierda se gestionan Proyectos y DBs con los correspondientes menús desplegables.

Las opciones concretas de los Proyectos están consolidadas bajo el botón del engranaje **⚙**:

| Acción Proyecto | Opción en Menú ⚙ |
|-----------------|------------------|
| Nuevo proyecto  | **➕ New Project**  |
| Renombrar       | **✏️ Rename**     |
| Exportar a JSON | **📤 Export**     |
| Importar JSON   | **📥 Import**     |
| Eliminar        | **🗑️ Delete**     |

### Menú de Información (esquina inferior)
Controla qué información se muestra en los nodos:
- **Power (MW)**: Consumo energético
- **Ingredients**: Materiales de entrada con tasas
- **Output Rate**: Tasa de producción de salida
- **Belt Flow**: Etiquetas de flujo en las conexiones

---

## Exportar e Importar Proyectos

### Formato JSON (v2)

```json
{
    "version": 2,
    "project_name": "Mi Fábrica",
    "groups": [
        {"id": 1, "name": "Grupo Hierro", "pos_x": 100, "pos_y": 200, "is_collapsed": 0}
    ],
    "nodes": [
        {"id": 1, "machine_id": 7, "recipe_id": 1, "group_id": 1,
         "pos_x": 150, "pos_y": 250, "clock_speed": 1.0}
    ],
    "connections": [
        {"id": 1, "source_node_id": 1, "target_node_id": 2,
         "source_port_idx": 0, "target_port_idx": 0, "material_id": 2}
    ]
}
```

- **Exportar**: Guarda el proyecto actual con todos sus grupos, nodos y conexiones.
- **Importar**: Crea un nuevo proyecto con un nombre único. Los IDs se remapean automáticamente.
- **Compatibilidad**: Los archivos v1 (sin grupos) se importan correctamente.

---

## Internacionalización

El módulo `i18n.py` proporciona soporte bilingüe (Inglés/Español):

- Todas las cadenas de la UI están centralizadas en un diccionario `_STRINGS`.
- El botón **🇺🇸 EN / 🇪🇸 ES** en la barra de herramientas alterna el idioma.
- La preferencia se guarda en la base de datos y se restaura al reiniciar.

### Añadir un Nuevo Idioma

1. Añadir una nueva clave al diccionario `_STRINGS` en `i18n.py`:
```python
_STRINGS = {
    "en": { ... },
    "es": { ... },
    "fr": {  # ← Nuevo idioma
        "app_title": "PLANIFICATEUR SATISFACTORY",
        ...
    }
}
```
2. Actualizar la lógica de toggle en `_on_toggle_language`.

---

## Registro de Logs

La aplicación usa el módulo estándar `logging` de Python:

- **Consola**: Todos los mensajes `INFO` y superiores.
- **Archivo**: `error.log` en la raíz del proyecto.
- **Formato**: `2026-03-09 10:00:00 [INFO] satisfactory_planner: mensaje`

### Niveles Usados

| Nivel | Uso |
|-------|-----|
| `INFO` | Inicialización de DB, migraciones, importación/exportación |
| `ERROR` | Fallos en exportar/importar, errores de DB |
| `WARNING` | Reservado para migraciones problemáticas |

---

## Preguntas Frecuentes

### ¿Cómo reinicio la base de datos?
Cierra la aplicación y elimina el archivo `satisfactory.db`. Al reiniciar se creará una nueva base de datos con los datos del juego precargados.

### ¿Puedo usar velocidades de reloj superiores a 250%?
No. El campo acepta valores entre 0.01 y 2.50 (1% – 250%), que es el rango oficial del juego.

### ¿Por qué una conexión aparece en rojo?
Significa **material incompatible**: la salida de la máquina origen no coincide con lo que necesita la máquina destino. Revisa las recetas seleccionadas.

### ¿Cómo cambio el estilo de las líneas de conexión?
En la barra de herramientas superior, usa el desplegable **LINE STYLE**:
- **Redondeado (Bezier)**: Curvas suaves (por defecto)
- **Recto**: Líneas directas
- **Ortogonal (Manhattan)**: Líneas con ángulos de 90°

### ¿Se guardan los cambios automáticamente?
Sí. Los cambios se persisten en la DB al cerrar la aplicación o al cambiar de proyecto.

---

*Documentación generada para Satisfactory Planner v2.0*
*Última actualización: Marzo 2026*
