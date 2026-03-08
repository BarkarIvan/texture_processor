import unittest

from ui.editor_widget import EditorWidget


class ScaleUnitConversionTests(unittest.TestCase):
    def test_meter_unit_keeps_value(self):
        self.assertAlmostEqual(EditorWidget.scale_length_to_meters(1.0, "m"), 1.0)

    def test_ten_centimeter_unit_converts_to_meters(self):
        self.assertAlmostEqual(EditorWidget.scale_length_to_meters(1.0, "cm10"), 0.1)

    def test_one_centimeter_unit_converts_to_meters(self):
        self.assertAlmostEqual(EditorWidget.scale_length_to_meters(1.0, "cm1"), 0.01)

    def test_invalid_unit_falls_back_to_meters(self):
        self.assertAlmostEqual(EditorWidget.scale_length_to_meters(2.5, "unknown"), 2.5)


if __name__ == "__main__":
    unittest.main()
