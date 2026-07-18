import unittest

import pygame

from piclock.config import Circle, Config, NetworkConfig
from piclock.input import Dispatcher, InputRouter


class InputControlTests(unittest.TestCase):
    def setUp(self):
        self.actions = []
        self.dispatcher = Dispatcher()
        for action in (
            "next_design",
            "prev_design",
            "open_network_settings",
            "network_tap",
        ):
            self.dispatcher.on(
                action,
                lambda *args, action=action: self.actions.append((action, args)),
            )
        config = Config(
            width=120,
            height=200,
            top=Circle(60, 60, 40),
            network=NetworkConfig(long_press_seconds=2.0),
        )
        self.router = InputRouter(config, self.dispatcher)

    @staticmethod
    def mouse_event(kind, pos):
        return pygame.event.Event(kind, button=1, pos=pos)

    def test_short_dial_tap_still_selects_next_design(self):
        self.router.process([self.mouse_event(pygame.MOUSEBUTTONDOWN, (60, 60))], now=10.0)
        self.router.process([self.mouse_event(pygame.MOUSEBUTTONUP, (60, 60))], now=10.3)

        self.assertEqual(self.actions, [("next_design", ())])

    def test_long_press_opens_network_settings_and_suppresses_tap(self):
        self.router.process([self.mouse_event(pygame.MOUSEBUTTONDOWN, (60, 60))], now=10.0)
        self.router.process([], now=11.9)
        self.assertEqual(self.actions, [])

        self.router.process([], now=12.1)
        self.router.process([self.mouse_event(pygame.MOUSEBUTTONUP, (60, 60))], now=12.2)

        self.assertEqual(self.actions, [("open_network_settings", ())])

    def test_pointer_movement_cancels_long_press_and_keeps_swipe(self):
        self.router.process([self.mouse_event(pygame.MOUSEBUTTONDOWN, (60, 60))], now=10.0)
        motion = pygame.event.Event(pygame.MOUSEMOTION, pos=(90, 60), buttons=(1, 0, 0))
        self.router.process([motion], now=10.2)
        self.router.process([], now=13.0)
        self.router.process([self.mouse_event(pygame.MOUSEBUTTONUP, (90, 60))], now=13.1)

        self.assertEqual(self.actions, [("prev_design", ())])

    def test_modal_tap_is_routed_to_network_panel(self):
        self.router.set_settings_open(True)
        self.router.process([self.mouse_event(pygame.MOUSEBUTTONDOWN, (50, 75))], now=10.0)
        self.router.process([self.mouse_event(pygame.MOUSEBUTTONUP, (50, 75))], now=10.1)

        self.assertEqual(self.actions, [("network_tap", ((50, 75),))])


if __name__ == "__main__":
    unittest.main()
