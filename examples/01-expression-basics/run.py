"""Example 01: QGIS expression basics."""
# These expressions can be used in QGIS Field Calculator or Filter

expressions = {
    "buffer_distance": "buffer($geometry, 100)",
    "nearest_feature": "overlay_nearest('layers', $geometry, limit:=5)",
    "area_hectares": "area($geometry) / 10000",
    "centroid_x": "x(centroid($geometry))",
    "centroid_y": "y(centroid($geometry))",
}

print("QGIS Expression Basics:")
print("=" * 40)
for name, expr in expressions.items():
    print(f"  {name}:")
    print(f"    {expr}")
    print()
