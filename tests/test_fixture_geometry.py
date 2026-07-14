import json
import tempfile
import unittest
from pathlib import Path

from piclock.config import Circle, bundled_config_path, load_config_files


class FixtureGeometryTests(unittest.TestCase):
    def test_bundled_json_defines_the_complete_device_geometry(self):
        cfg = load_config_files([bundled_config_path()])
        self.assertEqual(cfg.top, Circle(cx=224, cy=260, r=200))
        self.assertEqual(cfg.bottom, Circle(cx=210, cy=650, r=150))
        self.assertEqual(cfg.fixture_border_px, 0)
        self.assertEqual(cfg.rotate, 90)
        self.assertEqual(cfg.touch_rotate, 90)
        self.assertAlmostEqual(cfg.circle_y_scale, 0.925)

    def test_cad_measurements_are_loaded_from_json(self):
        cfg = load_config_files([bundled_config_path()])
        self.assertEqual((cfg.enclosure.width_mm, cfg.enclosure.height_mm), (102.0, 165.0))
        self.assertEqual(
            (cfg.enclosure.dial.left_mm, cfg.enclosure.dial.top_mm,
             cfg.enclosure.dial.diameter_mm),
            (14.9954, 16.4983, 76.0),
        )
        self.assertEqual(
            (cfg.enclosure.pendulum.left_mm, cfg.enclosure.pendulum.top_mm,
             cfg.enclosure.pendulum.diameter_mm),
            (29.0742, 107.4681, 48.5),
        )

    def test_partial_device_override_changes_only_requested_values(self):
        with tempfile.TemporaryDirectory() as root:
            override = Path(root, "override.json")
            override.write_text(json.dumps({
                "display": {"circle_y_scale": 0.91},
                "layout": {
                    "dial": {"center": [221, 254]},
                    "pendulum": {"center": [221, 646]},
                },
            }), encoding="utf-8")
            cfg = load_config_files([bundled_config_path(), override])

        self.assertEqual(cfg.top, Circle(cx=221, cy=254, r=200))
        self.assertEqual(cfg.bottom, Circle(cx=221, cy=646, r=150))
        self.assertEqual(cfg.width, 480)
        self.assertAlmostEqual(cfg.circle_y_scale, 0.91)

    def test_asset_requirements_are_configurable(self):
        cfg = load_config_files([bundled_config_path()])
        self.assertEqual(cfg.design_assets.dial_canvas, (480, 480))
        self.assertEqual(cfg.design_assets.pendulum_canvas, (300, 400))
        self.assertEqual(cfg.dial_diameters.maximum, 500)
        self.assertEqual(cfg.pendulum_diameters.minimum, 260)


if __name__ == "__main__":
    unittest.main()
