"""
ui/i18n.py
Simple internationalisation (i18n) module for English and Spanish.
"""

_current_lang = "en"

_STRINGS = {
    "en": {
        "app_title": "SATISFACTORY PLANNER",
        "sidebar_toggle": "☰ SIDEBAR",
        "machine_library": "MACHINE LIBRARY",
        "project": "PROJECT",
        "line_style": "LINE STYLE",
        "lang_toggle": "🇺🇸 EN",
        "ready": "Ready — right-drag: pan, scroll: zoom, double-click: place",
        "status_bar": "Nodes: {}   Connections: {}   | middle-drag: pan   scroll: zoom   drag port→port: connect   right-click: delete",
        "nodes": "Nodes",
        "connections": "Connections",
        "pan_help": "middle-drag: pan",
        "zoom_help": "scroll: zoom",
        "connect_help": "drag port→port: connect",
        "delete_help": "right-click: delete",
        "new_proj": "New Project",
        "rename_proj": "Rename Project",
        "delete_proj_title": "Delete Project",
        "delete_proj_conf": "Are you sure you want to delete '{}'?\nThis will remove all nodes and connections permanently.",
        "export_proj": "Export Project",
        "import_proj": "Import Project",
        "select_recipe": "— select recipe —",
        "items_min": "items/min",
        "items_min_short": "/min",
        "extraction": "EXTRACTION",
        "production": "PRODUCTION",
        "logistics": "LOGISTICS",
        "other": "OTHER",
        "double_click_place": "Double-click to place",
        "style_rounded": "Rounded (Bezier)",
        "style_straight": "Straight",
        "style_manhattan": "Orthogonal (Manhattan)",
        "project_switched": "Project switched to: {}",
        "project_deleted": "Project '{}' deleted.",
        "export_success": "Project exported to {}",
        "export_failed": "Export failed!",
        "import_success": "Project imported from {}",
        "import_failed": "Import failed!",
        "show_info": "SHOW INFO",
        "info_power": "Power (MW)",
        "info_inputs": "Ingredients",
        "info_output": "Output Rate",
        "info_belts": "Belt Flow",
        "set_clock": "Set Clock Speed",
        "delete": "Delete",
        "delete_conn": "Delete Connection",
        "mat_mismatch": "! MATERIAL MISMATCH !",
        "project_u": "Project",
    },
    "es": {
        "app_title": "PLANIFICADOR SATISFACTORY",
        "sidebar_toggle": "☰ BARRA LATERAL",
        "machine_library": "BIBLIOTECA DE MÁQUINAS",
        "project": "PROYECTO",
        "line_style": "ESTILO DE LÍNEA",
        "lang_toggle": "🇪🇸 ES",
        "ready": "Listo — click-derecho: desplazar, scroll: zoom, doble-click: colocar",
        "status_bar": "Nodos: {}   Conexiones: {}   | click-central: desplazar   scroll: zoom   arrastrar puerto→puerto: conectar   click-derecho: borrar",
        "nodes": "Nodos",
        "connections": "Conexiones",
        "pan_help": "click-central: desplazar",
        "zoom_help": "scroll: zoom",
        "connect_help": "arrastrar puerto→puerto: conectar",
        "delete_help": "click-derecho: borrar",
        "new_proj": "Nuevo Proyecto",
        "rename_proj": "Renombrar Proyecto",
        "delete_proj_title": "Eliminar Proyecto",
        "delete_proj_conf": "¿Estás seguro de que quieres eliminar '{}'?\nEsto borrará todos los nodos y conexiones permanentemente.",
        "export_proj": "Exportar Proyecto",
        "import_proj": "Importar Proyecto",
        "select_recipe": "— seleccionar receta —",
        "items_min": "objetos/min",
        "items_min_short": "/min",
        "extraction": "EXTRACCIÓN",
        "production": "PRODUCCIÓN",
        "logistics": "LOGÍSTICA",
        "other": "OTROS",
        "double_click_place": "Doble-click para colocar",
        "style_rounded": "Redondeado (Bezier)",
        "style_straight": "Recto",
        "style_manhattan": "Ortogonal (Manhattan)",
        "project_switched": "Proyecto cambiado a: {}",
        "project_deleted": "Proyecto '{}' eliminado.",
        "export_success": "Proyecto exportado a {}",
        "export_failed": "¡Error al exportar!",
        "import_success": "Proyecto importado de {}",
        "import_failed": "¡Error al importar!",
        "show_info": "MOSTRAR INFO",
        "info_power": "Energía (MW)",
        "info_inputs": "Ingredientes",
        "info_output": "Producción",
        "info_belts": "Flujo Belts",
        "set_clock": "Ajustar Velocidad",
        "delete": "Eliminar",
        "delete_conn": "Eliminar Conexión",
        "mat_mismatch": "! MATERIAL INCOMPATIBLE !",
        "project_u": "Proyecto",
    }
}

def set_language(lang_code: str):
    global _current_lang
    if lang_code in _STRINGS:
        _current_lang = lang_code

def get_language() -> str:
    return _current_lang

def tr(key: str, *args) -> str:
    """Translate a key to the current language."""
    text = _STRINGS.get(_current_lang, _STRINGS["en"]).get(key, key)
    if args:
        return text.format(*args)
    return text
