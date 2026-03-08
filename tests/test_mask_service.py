import unittest

from core.mask_service import remove_mask_entry, upsert_mask_entry


class MaskServiceTests(unittest.TestCase):
    def test_upsert_updates_existing_mask(self):
        masks = [{
            "id": 1,
            "points": [(0, 0)],
            "real_width": 1.0,
            "original_width": 100.0,
            "color": "#ffffff",
        }]
        updated, mask_id = upsert_mask_entry(
            masks,
            mask_id=1,
            points=[(1, 1)],
            real_width=2.0,
            original_width=200.0,
            color_factory=lambda _: "#000000",
        )
        self.assertEqual(mask_id, 1)
        self.assertEqual(updated[0]["points"], [(1, 1)])
        self.assertEqual(updated[0]["real_width"], 2.0)
        self.assertEqual(updated[0]["original_width"], 200.0)
        self.assertEqual(updated[0]["color"], "#ffffff")

    def test_upsert_creates_new_mask_with_generated_color(self):
        updated, mask_id = upsert_mask_entry(
            [],
            mask_id=None,
            points=[(1, 1)],
            real_width=2.0,
            original_width=200.0,
            color_factory=lambda _: "#123456",
        )
        self.assertEqual(mask_id, 1)
        self.assertEqual(updated[0]["id"], 1)
        self.assertEqual(updated[0]["color"], "#123456")

    def test_remove_mask_entry(self):
        masks = [{"id": 1}, {"id": 2}]
        remaining = remove_mask_entry(masks, mask_id=1)
        self.assertEqual([m["id"] for m in remaining], [2])


if __name__ == "__main__":
    unittest.main()
