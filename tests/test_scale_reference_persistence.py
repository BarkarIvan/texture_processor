import unittest

from ui.main_window import MainWindow


class ScaleReferencePersistenceTests(unittest.TestCase):
    def test_normalize_scale_reference_unit_accepts_known_values(self):
        self.assertEqual(MainWindow.normalize_scale_reference_unit("m"), "m")
        self.assertEqual(MainWindow.normalize_scale_reference_unit("cm10"), "cm10")
        self.assertEqual(MainWindow.normalize_scale_reference_unit("cm1"), "cm1")

    def test_normalize_scale_reference_unit_falls_back_to_meters(self):
        self.assertEqual(MainWindow.normalize_scale_reference_unit("unknown"), "m")
        self.assertEqual(MainWindow.normalize_scale_reference_unit(None), "m")

    def test_normalize_scale_reference_length_enforces_minimum(self):
        self.assertEqual(MainWindow.normalize_scale_reference_length(1.0), 1.0)
        self.assertEqual(MainWindow.normalize_scale_reference_length(0.0), 0.01)
        self.assertEqual(MainWindow.normalize_scale_reference_length("bad"), 1.0)


if __name__ == "__main__":
    unittest.main()
