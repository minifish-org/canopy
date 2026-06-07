import unittest

from canopy.audit import audit_from_path_details, audit_route_geometry


class AuditTests(unittest.TestCase):
    def test_audit_from_road_class_details(self):
        coords = [
            [103.9000, 1.3000],
            [103.9010, 1.3000],
            [103.9020, 1.3000],
            [103.9030, 1.3000],
        ]
        details = {
            "road_class": [
                [0, 2, "CYCLEWAY"],
                [2, 3, "RESIDENTIAL"],
            ]
        }

        audit = audit_from_path_details(coords, details)

        self.assertGreater(audit["car_free_pct"], 60)
        self.assertLess(audit["on_road_pct"], 40)
        self.assertTrue(audit["by_road_class"]["RESIDENTIAL"]["on_road"])
        self.assertFalse(audit["by_road_class"]["CYCLEWAY"]["on_road"])

    def test_audit_geometry_without_details_is_explicit(self):
        geometry = {
            "type": "LineString",
            "coordinates": [[103.9, 1.3], [103.901, 1.3]],
        }

        audit = audit_route_geometry(geometry)

        self.assertIsNone(audit["car_free_pct"])
        self.assertIn("coordinates only", audit["note"])


if __name__ == "__main__":
    unittest.main()
