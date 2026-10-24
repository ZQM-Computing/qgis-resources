"""Pattern 05: Batch processing — iterate over a folder."""
import os, glob

def batch_process(folder, algo="native:buffer", dist=100):
    results = []
    for f in glob.glob(os.path.join(folder, "*.gpkg")):
        r = processing.run(algo, {"INPUT": f, "DISTANCE": dist, "OUTPUT": "memory:"})["OUTPUT"]
        results.append(r)
    return results

if __name__ == "__main__":
    print("Pattern 05: batch processing ready")
