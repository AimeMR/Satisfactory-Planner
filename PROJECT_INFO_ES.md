# Satisfactory Planner 🚀🏙️

Una aplicación sofisticada de planificación de fábricas basada en nodos para **Satisfactory**, diseñada para ayudar a los Pioneros a diseñar, optimizar y visualizar sus líneas de producción con precisión.

> **🚀 Nota sobre la Evolución del Proyecto:** El estado actual de la aplicación sirve como la base interactiva. En el futuro, el proyecto evolucionará para convertirse en un **Generador Automático de Fábricas**. La aplicación preguntará al usuario qué material final desea producir (y a qué tasa), y creará, conectará y optimizará automáticamente todas las líneas de máquinas necesarias para conseguirlo.

## 🌟 Características Principales

- **Canvas Interactivo**: Un potente editor basado en nodos utilizando `PySide6` para colocar y conectar máquinas de producción.
- **Estadísticas en Tiempo Real**: Cálculo instantáneo de ratios de producción/consumo, flujo de objetos (objetos/min) y requisitos de energía.
- **Base de Datos Completa**: Precargada con todos los materiales, máquinas y recetas desde los **Niveles 1 al 8** y la **Fase 4** del Ascensor Espacial.
- **Soporte Multi-Base de Datos**: Organiza tus flujos de trabajo en archivos `.db` separados, gestionados dentro de la carpeta `databases/`.
- **Elementos Personalizados**: Añade fácilmente tus propios Materiales, Máquinas y Recetas personalizadas directamente desde la interfaz para planificar configuraciones con mods o hipotéticas.
- **Soporte Multi-Proyecto**: Crea, guarda y cambia entre múltiples diseños de fábricas sin problemas dentro de cualquier base de datos.
- **Interfaz Personalizable**:
    - **Visibilidad Global**: Alterna estadísticas de energía, entradas, salidas y flujo de cintas mediante un elegante menú con diseño glassmorphism.
    - **Espacio de Trabajo Optimizado**: Barra de herramientas superior limpia con acciones de proyecto consolidadas, estilos de línea y una barra lateral colapsable con un botón fijo.
    - **Multi-Idioma**: Completamente localizado en Inglés y Español.
    - **Aislamiento**: Cada proyecto tiene su propio entorno aislado para la colocación de máquinas y conexiones.

## 🛠️ Stack Técnico

- **Lenguaje**: Python 3.10+
- **Framework de UI**: PySide6 (Qt para Python).
- **Base de Datos**: SQLite con un esquema de múltiples entradas/salidas para recetas complejas.
- **Arquitectura**: Capas separadas de Lógica (cálculos), UI (nodos/escena) y Base de Datos (CRUD/semilla).

## 📁 Estructura del Proyecto

- `databases/`: Directorio donde se almacenan todos los archivos de bases de datos SQLite (como `satisfactory.db`).
- `database/`: Esquema SQLite, lógica de semillado (`seed_data.py`), gestión de múltiples DBs y operaciones CRUD (`crud.py`).
- `ui/`: Ventana principal, gráficos de nodos personalizados (`machine_node.py`) y renderizado de conexiones.
- `logic/`: Motor de cálculo para ratios de producción y eficiencia.
- `i18n/`: Claves de traducción y gestión de localización.

## 🚀 Cómo Ejecutar

1. **Instalar Dependencias**:
   ```bash
   pip install pyside6
   ```
2. **Lanzar la Aplicación**:
   ```bash
   python main.py
   ```

---
*Construido para la comunidad de Pioneros. ¡La eficiencia es lo primero!*
