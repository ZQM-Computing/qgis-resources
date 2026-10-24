"""Pattern 04: CRS transforms — batch reproject layers."""
def crs_transform(layer_path, target_crs="EPSG:4326"):
    out = processing.run("native:reprojectlayer", {"INPUT": layer_path, "TARGET_CRS": target_crs, "OUTPUT": "memory:"})["OUTPUT"]
    return out

if __name__ == "__main__":
    print("Pattern 04: CRS transforms ready")
