import json
import tempfile
import unittest
from pathlib import Path

from piclock.config import DiameterRange
from piclock.designs import DesignSet, Theme


class ThemeLayoutTests(unittest.TestCase):
    def test_existing_designs_keep_original_circle_sizes(self):
        theme = Theme.from_dict({})
        self.assertEqual(theme.dial_diameter, 400)
        self.assertEqual(theme.bottom.diameter, 300)

    def test_custom_circle_sizes_are_loaded(self):
        theme = Theme.from_dict({
            "dial": {"diameter": 500},
            "bottom": {"diameter": 340},
        })
        self.assertEqual(theme.dial_diameter, 500)
        self.assertEqual(theme.bottom.diameter, 340)

    def test_circle_sizes_are_clamped_to_safe_renderer_limits(self):
        theme = Theme.from_dict({
            "dial": {"diameter": 900},
            "bottom": {"diameter": 20},
        })
        self.assertEqual(theme.dial_diameter, 500)
        self.assertEqual(theme.bottom.diameter, 260)

    def test_circle_size_limits_come_from_clock_configuration(self):
        theme = Theme.from_dict(
            {"dial": {"diameter": 900}, "bottom": {"diameter": 20}},
            dial_diameters=DiameterRange(420, 430, 480),
            pendulum_diameters=DiameterRange(280, 310, 360),
        )
        self.assertEqual(theme.dial_diameter, 480)
        self.assertEqual(theme.bottom.diameter, 280)

    def test_unique_folder_slugs_are_not_hidden_by_duplicate_display_names(self):
        with tempfile.TemporaryDirectory() as root:
            for slug in ("first", "second"):
                folder = Path(root, slug)
                folder.mkdir()
                folder.joinpath("theme.json").write_text(
                    json.dumps({"name": "Shared Name"}), encoding="utf-8"
                )
            designs = DesignSet.scan(root)
        self.assertEqual(
            [Path(design.path).name for design in designs.designs],
            ["first", "second"],
        )

    def test_later_root_overrides_duplicate_folder_slug(self):
        with tempfile.TemporaryDirectory() as root:
            system_root = Path(root, "system")
            user_root = Path(root, "user")
            system_folder = system_root / "Night"
            user_folder = user_root / "night"
            system_folder.mkdir(parents=True)
            user_folder.mkdir(parents=True)
            system_folder.joinpath("theme.json").write_text(
                json.dumps({"name": "Bundled Night"}), encoding="utf-8"
            )
            user_folder.joinpath("theme.json").write_text(
                json.dumps({"name": "User Night"}), encoding="utf-8"
            )

            designs = DesignSet.scan([str(system_root), str(user_root)])

        self.assertEqual(len(designs.designs), 1)
        self.assertEqual(designs.designs[0].name, "User Night")
        self.assertEqual(Path(designs.designs[0].path).name, "night")


if __name__ == "__main__":
    unittest.main()
