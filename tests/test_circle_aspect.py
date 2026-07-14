import unittest

import pygame

from piclock.app import _aspect_correct_circle
from piclock.config import Circle, Config
from piclock.input import Dispatcher, InputRouter


class CircleAspectTests(unittest.TestCase):
    def test_rendered_circle_is_scaled_around_unchanged_center(self):
        surface = pygame.Surface((120, 120), pygame.SRCALPHA)
        surface.fill((0, 0, 0, 255))
        circle = Circle(cx=60, cy=60, r=40)
        pygame.draw.circle(surface, (255, 255, 255, 255),
                           (circle.cx, circle.cy), circle.r)

        _aspect_correct_circle(surface, circle, 0.5)

        pixels = [
            (x, y)
            for y in range(surface.get_height())
            for x in range(surface.get_width())
            if surface.get_at((x, y))[:3] != (0, 0, 0)
        ]
        xs = [point[0] for point in pixels]
        ys = [point[1] for point in pixels]
        width = max(xs) - min(xs) + 1
        height = max(ys) - min(ys) + 1

        self.assertAlmostEqual(height / width, 0.5, delta=0.03)
        self.assertAlmostEqual((min(xs) + max(xs)) / 2, circle.cx, delta=1.0)
        self.assertAlmostEqual((min(ys) + max(ys)) / 2, circle.cy, delta=1.0)

    def test_touch_hit_area_uses_corrected_ellipse(self):
        cfg = Config(circle_y_scale=0.5, top=Circle(cx=60, cy=60, r=40))
        router = InputRouter(cfg, Dispatcher())

        self.assertTrue(router._in_top_circle((60, 79)))
        self.assertFalse(router._in_top_circle((60, 81)))
        self.assertTrue(router._in_top_circle((99, 60)))


if __name__ == "__main__":
    unittest.main()
