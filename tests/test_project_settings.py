import unittest

from core.project_settings import normalize_project_settings


class ProjectSettingsTests(unittest.TestCase):
    def test_defaults_for_missing_fields(self):
        settings = normalize_project_settings({})
        self.assertEqual(settings["atlas_density"], 512.0)
        self.assertEqual(settings["atlas_size"], 2048)
        self.assertEqual(settings["scale_reference_length"], 1.0)
        self.assertEqual(settings["scale_reference_unit"], "m")

    def test_invalid_values_fall_back_to_defaults(self):
        settings = normalize_project_settings({
            "atlas_density": "bad",
            "atlas_size": "bad",
            "scale_reference_length": "bad",
            "scale_reference_unit": "bad",
        })
        self.assertEqual(settings["atlas_density"], 512.0)
        self.assertEqual(settings["atlas_size"], 2048)
        self.assertEqual(settings["scale_reference_length"], 1.0)
        self.assertEqual(settings["scale_reference_unit"], "m")

    def test_scale_reference_length_has_minimum(self):
        settings = normalize_project_settings({"scale_reference_length": 0.0})
        self.assertEqual(settings["scale_reference_length"], 0.01)


if __name__ == "__main__":
    unittest.main()
