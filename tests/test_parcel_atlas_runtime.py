"""Actual QGIS/Poppler tests for the synthetic Rank 1 parcel atlas.

Core pytest without QGIS skips this module's runtime class. The QGIS workflow
executes it explicitly with system Python and Poppler. No network is required.
"""
import csv
from contextlib import closing
import gc
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest import mock

try:
    from qgis.core import (
        QgsApplication, QgsExpression, QgsLayoutExporter, QgsMapRendererParallelJob,
        QgsMapSettings, QgsPrintLayout, QgsProject, QgsReadWriteContext, QgsRectangle,
    )
    from qgis.PyQt.QtCore import QSize
    from qgis.PyQt.QtXml import QDomDocument
except ImportError:
    QgsApplication = None

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "exhibit-production/fixtures/geopandas-handoff"


@unittest.skipIf(QgsApplication is None, "QGIS Python bindings required; run the QGIS runtime job")
class ParcelAtlasRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QgsApplication.instance()
        cls.owns_app = cls.app is None
        if cls.owns_app:
            cls.app = QgsApplication([], False)
            cls.app.initQgis()
        spec = importlib.util.spec_from_file_location("rank1_atlas", ROOT / "exhibit-production/parcel_atlas.py")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        cls.temp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.temp.name)
        cls.input_hashes = {p.name: cls.module.sha256(p) for p in FIXTURE.iterdir()}
        output = cls.module.build_atlas(FIXTURE, cls.work / "original", "2026-11-14")
        cls.output = cls.work / "relocated"
        output.rename(cls.output)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()
        gc.collect()
        if cls.owns_app:
            cls.app.exitQgis()

    def new_handoff(self, suffix):
        target = self.work / self._testMethodName / suffix
        shutil.copytree(FIXTURE, target)
        return target

    def rehash(self, handoff):
        path = handoff / "exhibit_manifest.json"
        manifest = json.loads(path.read_text())
        for entry in manifest["file_inventory"]:
            entry["sha256"] = self.module.sha256(handoff / entry["filename"])
            entry["bytes"] = (handoff / entry["filename"]).stat().st_size
        path.write_text(json.dumps(manifest))

    def rewrite_rows(self, handoff, change):
        path = handoff / "parcel_screening.json"
        report = json.loads(path.read_text())
        change(report["rows"])
        path.write_text(json.dumps(report))
        with (handoff / "parcel_constraints.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(report["rows"][0]))
            writer.writeheader()
            writer.writerows(report["rows"])
        self.rehash(handoff)

    def reject(self, handoff, pattern):
        output = handoff.parent / "rejected-output"
        with self.assertRaisesRegex(ValueError, pattern):
            self.module.build_atlas(handoff, output, "2026-11-14")
        self.assertFalse(output.exists())
        self.assertFalse(list(handoff.parent.glob(".parcel-atlas-*")))

    def test_pdf_page_manifest_and_source_bytes(self):
        with (self.output / "delivery_manifest.csv").open(newline="") as stream:
            pages = list(csv.DictReader(stream))
        self.assertEqual([p["parcel_id"] for p in pages], ["DEMO-P1", "DEMO-P2"])
        self.assertEqual([p["has_data_gap"] for p in pages], ["0", "1"])
        self.assertEqual(pages[1]["wetland_status"], "no_source_coverage")
        self.assertEqual(pages[1]["flood_status"], "partial_source_coverage")
        sources = json.loads((self.output / "source_register.json").read_text())
        for p in pages:
            p["has_data_gap"] = int(p["has_data_gap"])
            self.assertEqual(json.loads(p["source_register_snapshot"]), sources)
        self.module.verify_pdf(self.output / "EnvConstraints_Atlas.pdf", pages, sources)
        run = json.loads((self.output / "atlas_run.json").read_text())
        self.assertEqual(run["page_count"], 2)
        for entry in run["files"]:
            p = self.output / entry["filename"]
            self.assertEqual(entry["sha256"], self.module.sha256(p))
            self.assertEqual(entry["bytes"], p.stat().st_size)
        self.assertEqual(self.input_hashes, {p.name: self.module.sha256(p) for p in FIXTURE.iterdir()})

    def test_relocated_project_layout_and_xml_template(self):
        project = QgsProject()
        try:
            self.assertTrue(project.read(str(self.output / "Env_Constraints_Parcel_Atlas.qgz")))
            self.assertTrue(all(layer.isValid() for layer in project.mapLayers().values()))
            self.assertEqual(len(project.mapLayers()), 5)
            layout = project.layoutManager().layouts()[0]
            atlas = layout.atlas()
            main, inset = layout.itemById("main_map"), layout.itemById("inset_map")
            self.assertEqual(inset.overviews().asList()[0].linkedMap(), main)
            self.assertEqual(layout.itemById("scale_bar").linkedMap(), main)
            atlas.updateFeatures()
            self.assertTrue(atlas.beginRender())
            for pid in ("DEMO-P1", "DEMO-P2"):
                self.assertTrue(atlas.next())
                self.assertEqual(layout.reportContext().feature()["parcel_id"], pid)
                self.assertTrue(main.extent().contains(layout.reportContext().feature().geometry().boundingBox()))
            atlas.endRender()
            xml = (self.output / "Env_Constraints_Parcel_Atlas.qpt").read_text()
            self.assertNotIn(".parcel-atlas-", xml)
            self.assertIn("./atlas_data.gpkg", xml)
            document = QDomDocument()
            self.assertTrue(document.setContent(xml)[0])
            context = QgsReadWriteContext()
            context.setPathResolver(project.pathResolver())
            restored = QgsPrintLayout(project)
            _, success = restored.loadFromTemplate(document, context)
            self.assertTrue(success)
            self.assertEqual(len(restored.itemById("main_map").layers()), 5)
            self.assertIsNotNone(restored.atlas().coverageLayer())
            image = QgsLayoutExporter(layout).renderPageToImage(0, QSize(1000, 773))
            self.assertFalse(image.isNull())
        finally:
            project.clear()

    def test_gap_hatching_is_visible_over_another_constraint_fill(self):
        project = QgsProject()
        try:
            project.read(str(self.output / "Env_Constraints_Parcel_Atlas.qgz"))
            main = project.layoutManager().layouts()[0].itemById("main_map")
            layers = main.layers()
            def render(selected):
                settings = QgsMapSettings()
                settings.setDestinationCrs(project.crs())
                settings.setLayers(selected)
                # DEMO-P2: mapped flood indicator AND absent wetland coverage.
                settings.setExtent(QgsRectangle(500126, 3200020, 500149, 3200080))
                settings.setOutputSize(QSize(230, 600))
                job = QgsMapRendererParallelJob(settings)
                job.start()
                job.waitForFinished()
                return job.renderedImage()
            with_gap = render(layers)
            without_gap = render([layer for layer in layers if layer.name() != "Wetland coverage gap"])
            self.assertNotEqual(with_gap, without_gap, "Flood fill obscures the wetland coverage gap")
        finally:
            project.clear()

    def test_filter_retains_gap_only_parcels_and_filename_is_safe(self):
        manifest, sources, rows = self.module.read_handoff(FIXTURE)
        _, layers = self.module.prepare_layers(FIXTURE, manifest, rows)
        atlas = layers["atlas_parcels"]
        second = list(atlas.getFeatures())[1]
        second.setAttribute("has_indicator", 0)
        atlas.dataProvider().changeAttributeValues({second.id(): {atlas.fields().indexFromName("has_indicator"): 0}})
        project = QgsProject()
        project.setCrs(atlas.crs())
        try:
            layout = self.module.make_layout(project, layers, sources, "2026-11-14", True)
            layout.atlas().updateFeatures()
            self.assertTrue(layout.atlas().beginRender())
            filenames = []
            ids = []
            while layout.atlas().next():
                ids.append(layout.reportContext().feature()["parcel_id"])
                value = QgsExpression(self.module.EXPRESSIONS["filename"])
                filenames.append(value.evaluate(layout.createExpressionContext()))
            layout.atlas().endRender()
            self.assertEqual(ids, ["DEMO-P1", "DEMO-P2"])
            self.assertEqual(filenames, ["EnvConstraints_0001_DEMO-P1_20261114", "EnvConstraints_0002_DEMO-P2_20261114"])
        finally:
            project.clear()

    def test_refuse_existing_destination(self):
        before = self.module.sha256(self.output / "EnvConstraints_Atlas.pdf")
        with self.assertRaises(FileExistsError):
            self.module.build_atlas(FIXTURE, self.output, "2026-11-14")
        self.assertEqual(before, self.module.sha256(self.output / "EnvConstraints_Atlas.pdf"))

    def test_refuse_missing_register(self):
        handoff = self.new_handoff("input")
        (handoff / "source_register.json").unlink()
        self.reject(handoff, "complete flat")

    def test_refuse_missing_retrieval_date_even_with_updated_checksums(self):
        handoff = self.new_handoff("input")
        sources = json.loads((handoff / "source_register.json").read_text())
        sources[0]["accessed_utc"] = ""
        (handoff / "source_register.json").write_text(json.dumps(sources))
        report = json.loads((handoff / "parcel_screening.json").read_text())
        report["source_register"] = sources
        (handoff / "parcel_screening.json").write_text(json.dumps(report))
        self.rehash(handoff)
        self.reject(handoff, "accessed_utc")

    def test_refuse_checksum_tampering(self):
        handoff = self.new_handoff("input")
        (handoff / "LIMITATIONS.txt").write_text("tampered")
        self.reject(handoff, "checksum")

    def test_refuse_geographic_crs(self):
        handoff = self.new_handoff("input")
        path = handoff / "exhibit_manifest.json"
        manifest = json.loads(path.read_text())
        manifest["analysis_crs"] = "EPSG:4326"
        path.write_text(json.dumps(manifest))
        self.reject(handoff, "projected metre CRS")

    def test_refuse_mixed_layer_crs(self):
        handoff = self.new_handoff("input")
        with closing(sqlite3.connect(handoff / "parcel_screening.gpkg")) as connection:
            with connection:
                connection.execute("UPDATE gpkg_geometry_columns SET srs_id=4326 WHERE table_name='known_overlaps'")
        self.rehash(handoff)
        self.reject(handoff, "CRS mismatch")

    def test_refuse_incomplete_matrix(self):
        handoff = self.new_handoff("input")
        self.rewrite_rows(handoff, lambda rows: rows.pop())
        self.reject(handoff, "Incomplete parcel/type")

    def test_refuse_unknown_coverage_relabelled_as_negative(self):
        handoff = self.new_handoff("input")
        def change(rows):
            next(r for r in rows if r["status"] == "no_source_coverage")["status"] = "no_mapped_intersection"
        self.rewrite_rows(handoff, change)
        self.reject(handoff, "contradictory screening status")

    def test_refuse_csv_json_disagreement(self):
        handoff = self.new_handoff("input")
        path = handoff / "parcel_constraints.csv"
        path.write_text(path.read_text().replace("intersects", "no_mapped_intersection"))
        self.rehash(handoff)
        self.reject(handoff, "CSV/report screening value mismatch")

    def test_refuse_duplicate_parcel_geometry_ids(self):
        handoff = self.new_handoff("input")
        from qgis.core import QgsVectorLayer
        layer = QgsVectorLayer(str(handoff / "parcel_screening.gpkg") + "|layername=parcels", "parcels", "ogr")
        features = list(layer.getFeatures())
        self.assertTrue(layer.dataProvider().changeAttributeValues(
            {features[1].id(): {layer.fields().indexFromName("parcel_id"): "DEMO-P1"}}))
        del layer
        self.rehash(handoff)
        self.reject(handoff, "Duplicate parcel IDs")

    def test_refuse_nonfinite_numbers(self):
        handoff = self.new_handoff("input")
        self.rewrite_rows(handoff, lambda rows: rows[0].update(unknown_m2=float("nan")))
        self.reject(handoff, "Invalid screening number")

    def test_cli_failure_returns_useful_exit_code_without_crashing(self):
        handoff = self.new_handoff("input")
        (handoff / "source_register.json").unlink()
        result = subprocess.run([
            "/usr/bin/python3", str(ROOT / "exhibit-production/parcel_atlas.py"),
            str(handoff), str(handoff.parent / "cli-output"), "--date", "2026-11-14",
        ], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("complete flat", result.stderr)

    def test_failed_export_cleans_stage_and_preserves_input(self):
        output = self.work / self._testMethodName / "failed"
        with mock.patch.object(self.module, "verify_pdf", side_effect=ValueError("injected PDF validation failure")):
            with self.assertRaisesRegex(ValueError, "injected PDF"):
                self.module.build_atlas(FIXTURE, output, "2026-11-14")
        self.assertFalse(output.exists())
        self.assertFalse(list(output.parent.glob(".parcel-atlas-*")))
        self.assertEqual(self.input_hashes, {p.name: self.module.sha256(p) for p in FIXTURE.iterdir()})


if __name__ == "__main__":
    unittest.main()
