import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

from canopy.gpx import export_gpx


class GpxTests(unittest.TestCase):
    def test_export_dense_track(self):
        geometry = {
            "type": "LineString",
            "coordinates": [[103.9, 1.3], [103.901, 1.3], [103.902, 1.301]],
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_gpx(geometry, "Test Route", Path(tmpdir))
            tree = ET.parse(path)
            root = tree.getroot()
            points = root.findall(".//{http://www.topografix.com/GPX/1/1}trkpt")

        self.assertEqual(len(points), 3)
        self.assertEqual(points[0].attrib["lat"], "1.3")
        self.assertEqual(points[0].attrib["lon"], "103.9")


if __name__ == "__main__":
    unittest.main()
