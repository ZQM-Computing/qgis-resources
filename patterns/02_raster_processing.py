"""Pattern 02: Raster processing — reproject, clip, slope."""
def raster_processing(dem_path, boundary_path):
    dem = processing.run("gdal:warpreproject", {"INPUT": dem_path, "TARGET_CRS": "EPSG:32633", "OUTPUT": "memory:"})["OUTPUT"]
    clipped = processing.run("gdal:cliprasterbymasklayer", {"INPUT": dem, "MASK": boundary_path, "OUTPUT": "memory:"})["OUTPUT"]
    slope = processing.run("qgis:slope", {"INPUT": clipped, "OUTPUT": "memory:"})["OUTPUT"]
    return slope

if __name__ == "__main__":
    print("Pattern 02: raster processing ready")
