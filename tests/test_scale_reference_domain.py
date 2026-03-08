import unittest

from core.scale_reference import ScaleReference


class ScaleReferenceDomainTests(unittest.TestCase):
    def test_to_meters_for_meter_unit(self):
        self.assertAlmostEqual(ScaleReference(1.0, "m").to_meters(), 1.0)

    def test_to_meters_for_10cm_unit(self):
        self.assertAlmostEqual(ScaleReference(1.0, "cm10").to_meters(), 0.1)

    def test_to_meters_for_1cm_unit(self):
        self.assertAlmostEqual(ScaleReference(1.0, "cm1").to_meters(), 0.01)

    def test_unknown_unit_falls_back_to_meter(self):
        self.assertAlmostEqual(ScaleReference(2.5, "bad").to_meters(), 2.5)

    def test_non_positive_length_is_clamped(self):
        self.assertAlmostEqual(ScaleReference(0.0, "m").to_meters(), 1e-6)


if __name__ == "__main__":
    unittest.main()
