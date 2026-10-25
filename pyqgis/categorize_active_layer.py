"""
Apply a categorized renderer to the active vector layer, one colour per
distinct value of a chosen field.

Where to run: QGIS Python Console. Tested with QGIS 3.28+.

Change FIELD below to the field you want to classify before running. The
script reads the layer's actual distinct values, so it works on any field
with a manageable number of distinct values; it is not tied to a sample
dataset. Colours cycle through a small fixed palette when a field has more
distinct values than the palette holds.

Layer selection: the current layer in the Layers panel when one is active,
otherwise the first valid vector layer in the project. If the field is
missing, the script raises and lists the fields the layer actually has,
instead of applying a broken renderer.
"""

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsProject,
    QgsRendererCategory,
    QgsSymbol,
    QgsVectorLayer,
)
from qgis.PyQt.QtGui import QColor

FIELD = "zone"

PALETTE = [
    (102, 194, 165),
    (252, 141, 98),
    (141, 160, 203),
    (231, 138, 195),
    (166, 216, 84),
    (255, 217, 47),
    (229, 196, 148),
    (179, 179, 179),
]


def active_vector_layer():
    """Return the active vector layer, or the first valid one in the project."""
    project = QgsProject.instance()
    iface = globals().get("iface")
    if iface is not None:
        canvas = iface.mapCanvas()
        current = canvas.currentLayer() if canvas is not None else None
        if isinstance(current, QgsVectorLayer) and current.isValid():
            return current
    for layer in project.mapLayers().values():
        if isinstance(layer, QgsVectorLayer) and layer.isValid():
            return layer
    raise ValueError("No valid vector layer found in the current project")


def categorize_active_layer(field_name: str) -> int:
    """Categorize the active vector layer by field_name.

    Returns the number of categories applied.
    """
    layer = active_vector_layer()
    field_names = layer.fields().names()
    if field_name not in field_names:
        raise ValueError(
            f"Field {field_name!r} not found on layer {layer.name()!r}. "
            f"Available fields: {', '.join(field_names)}"
        )
    index = layer.fields().lookupField(field_name)
    values = [value for value in layer.uniqueValues(index) if value is not None]
    if not values:
        raise ValueError(
            f"Field {field_name!r} on layer {layer.name()!r} has no "
            "non-null values to categorize"
        )
    categories = []
    for position, value in enumerate(sorted(values, key=str)):
        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol.setColor(QColor(*PALETTE[position % len(PALETTE)]))
        categories.append(QgsRendererCategory(value, symbol, str(value)))
    layer.setRenderer(QgsCategorizedSymbolRenderer(field_name, categories))
    layer.triggerRepaint()
    return len(categories)


if __name__ in {"__main__", "__console__"}:
    applied = categorize_active_layer(FIELD)
    print(f"Categorized active layer by {FIELD!r}: {applied} categories applied")
