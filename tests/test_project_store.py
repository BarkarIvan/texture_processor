import unittest

from core.project_store import normalize_loaded_project, prepare_for_save


class ProjectStoreTests(unittest.TestCase):
    def test_prepare_for_save_writes_scale_reference_fields(self):
        saved = prepare_for_save(
            {"textures": {}, "items": []},
            scale_reference_length=0.5,
            scale_reference_unit="cm10",
        )
        self.assertEqual(saved["scale_reference_length"], 0.5)
        self.assertEqual(saved["scale_reference_unit"], "cm10")

    def test_normalize_loaded_project_backfills_scale_reference_fields(self):
        loaded = normalize_loaded_project({"textures": {}, "items": []})
        self.assertEqual(loaded["scale_reference_length"], 1.0)
        self.assertEqual(loaded["scale_reference_unit"], "m")

    def test_prepare_for_save_normalizes_invalid_unit(self):
        saved = prepare_for_save(
            {"textures": {}, "items": []},
            scale_reference_length=1.0,
            scale_reference_unit="bad",
        )
        self.assertEqual(saved["scale_reference_unit"], "m")


if __name__ == "__main__":
    unittest.main()
