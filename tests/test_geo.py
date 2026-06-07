import unittest

from canopy.geo import coerce_point, geometry_coordinates, haversine_m


class GeoTests(unittest.TestCase):
    def test_coerce_singapore_lat_lon_string(self):
        self.assertEqual(coerce_point("1.31978,103.90323"), (1.31978, 103.90323))

    def test_geometry_coordinates_accepts_feature(self):
        feature = {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "LineString",
                "coordinates": [[103.9, 1.3], [103.901, 1.301]],
            },
        }
        self.assertEqual(
            geometry_coordinates(feature), [(103.9, 1.3), (103.901, 1.301)]
        )

    def test_haversine_reasonable_for_short_segment(self):
        distance = haversine_m((1.3, 103.9), (1.3, 103.901))
        self.assertGreater(distance, 100)
        self.assertLess(distance, 120)


if __name__ == "__main__":
    unittest.main()
