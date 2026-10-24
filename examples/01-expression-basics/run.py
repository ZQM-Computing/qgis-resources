"""QGIS expression reference: expressions are evaluated by QGIS, not plain Python.

Paste an expression into QGIS Field Calculator or the expression editor only
after replacing example layer names and confirming geometry CRS and field names.
"""
expressions = {
    # Buffer distances use the layer CRS units, not always metres.
    "buffer_distance": "buffer($geometry, 100)",
    # Replace 'sites' with a real layer name; requires compatible CRSs.
    "nearest_feature": "overlay_nearest('sites', $geometry, limit:=5)",
    # Only label this as hectares when the project measurement result is m².
    # Verify project ellipsoid/measurement settings before using the conversion.
    "area_hectares_if_area_is_m2": "area($geometry) / 10000",
    # Centroid coordinates are in the geometry CRS; they are not automatically lon/lat.
    "centroid_x": "x(centroid($geometry))",
    "centroid_y": "y(centroid($geometry))",
}

if __name__ == "__main__":
    print("QGIS Expression Reference")
    print("=" * 40)
    for name, expression in expressions.items():
        print(f"{name}: {expression}")
    print("Review CRS, measurement ellipsoid, layer names, and field names before use.")
