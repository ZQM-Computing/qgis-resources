"""Pattern 03: Spatial joins — join attributes by location."""
def spatial_join(points_path, polygons_path):
    points = processing.run("native:joinattributesbylocation", {
        "INPUT": points_path, "JOIN": polygons_path,
        "PREDICATE": [0], "METHOD": 0, "OUTPUT": "memory:"
    })["OUTPUT"]
    return points

if __name__ == "__main__":
    print("Pattern 03: spatial joins ready")
