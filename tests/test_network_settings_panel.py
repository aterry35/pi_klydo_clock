import unittest

import pygame

from piclock.config import Circle
from piclock.layers.network_settings import NetworkSettingsPanel


class NetworkSettingsPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.font.init()

    def setUp(self):
        self.panel = NetworkSettingsPanel(Circle(240, 260, 200), 0.925)

    def _physical_center(self, rect):
        return (
            rect.centerx,
            260 + (rect.centery - 260) * 0.925,
        )

    def test_setup_requires_a_second_confirming_tap(self):
        self.assertIsNone(self.panel.handle_tap(self._physical_center(self.panel.setup_rect)))
        self.assertTrue(self.panel.confirming_reset)

        action = self.panel.handle_tap(self._physical_center(self.panel.confirm_rect))

        self.assertEqual(action, "start_hotspot")
        self.assertFalse(self.panel.confirming_reset)

    def test_cancel_returns_to_status_without_reset(self):
        self.panel.handle_tap(self._physical_center(self.panel.setup_rect))

        action = self.panel.handle_tap(self._physical_center(self.panel.cancel_rect))

        self.assertIsNone(action)
        self.assertFalse(self.panel.confirming_reset)

    def test_aspect_corrected_refresh_button_maps_back_to_logical_rect(self):
        action = self.panel.handle_tap(self._physical_center(self.panel.refresh_rect))

        self.assertEqual(action, "refresh")

    def test_busy_panel_ignores_destructive_action(self):
        self.panel.handle_tap(self._physical_center(self.panel.setup_rect))

        action = self.panel.handle_tap(
            self._physical_center(self.panel.confirm_rect),
            busy=True,
        )

        self.assertIsNone(action)
        self.assertTrue(self.panel.confirming_reset)


if __name__ == "__main__":
    unittest.main()
