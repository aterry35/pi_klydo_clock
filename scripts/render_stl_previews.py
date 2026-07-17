#!/usr/bin/env python3
"""Render deterministic documentation previews from the enclosure STL files."""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
PARTS = (
    ("clock_frame.stl", "Clock Frame", "#aeb5bf"),
    ("clock_face.stl", "Clock Face", "#e3a049"),
    ("clock_back.stl", "Clock Back", "#5e9b9a"),
)
STL_DTYPE = np.dtype(
    [("normal", "<f4", 3), ("vertices", "<f4", 9), ("attribute", "<u2")]
)


def load_binary_stl(path: Path) -> np.ndarray:
    with path.open("rb") as handle:
        handle.seek(80)
        count_bytes = handle.read(4)
        if len(count_bytes) != 4:
            raise ValueError(f"{path} is too short to be a binary STL")
        triangle_count = struct.unpack("<I", count_bytes)[0]
        triangles = np.fromfile(handle, dtype=STL_DTYPE, count=triangle_count)

    expected_size = 84 + triangle_count * STL_DTYPE.itemsize
    if path.stat().st_size != expected_size or len(triangles) != triangle_count:
        raise ValueError(f"{path} is not a supported binary STL")
    return triangles["vertices"].reshape(-1, 3, 3).astype(np.float64)


def mesh_size(triangles: np.ndarray) -> np.ndarray:
    vertices = triangles.reshape(-1, 3)
    return vertices.max(axis=0) - vertices.min(axis=0)


def rotate_for_preview(triangles: np.ndarray) -> np.ndarray:
    vertices = triangles.reshape(-1, 3)
    centered = triangles - (vertices.min(axis=0) + vertices.max(axis=0)) / 2
    yaw = np.radians(32)
    pitch = np.radians(-18)
    rotate_y = np.array(
        [[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]]
    )
    rotate_x = np.array(
        [[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)], [0, np.sin(pitch), np.cos(pitch)]]
    )
    return centered @ (rotate_x @ rotate_y).T


def shade(base_hex: str, intensity: float) -> tuple[int, int, int]:
    base = np.array([int(base_hex[index:index + 2], 16) for index in (1, 3, 5)])
    color = np.clip(base * intensity + 18, 0, 255)
    return tuple(int(channel) for channel in color)


def render_part(path: Path, title: str, base_color: str, output_path: Path) -> None:
    scale_factor = 2
    width, height = 500 * scale_factor, 650 * scale_factor
    model_top, model_bottom = 42 * scale_factor, 510 * scale_factor
    image = Image.new("RGB", (width, height), "#15181c")
    draw = ImageDraw.Draw(image)
    triangles = load_binary_stl(path)
    rotated = rotate_for_preview(triangles)

    projected = rotated[..., :2].copy()
    projected[..., 1] *= -1
    low = projected.reshape(-1, 2).min(axis=0)
    high = projected.reshape(-1, 2).max(axis=0)
    available = np.array([width - 76 * scale_factor, model_bottom - model_top])
    projection_scale = float(np.min(available / np.maximum(high - low, 1e-6)))
    projected *= projection_scale
    center = (projected.reshape(-1, 2).min(axis=0) + projected.reshape(-1, 2).max(axis=0)) / 2
    projected[..., 0] += width / 2 - center[0]
    projected[..., 1] += (model_top + model_bottom) / 2 - center[1]

    edges_a = rotated[:, 1] - rotated[:, 0]
    edges_b = rotated[:, 2] - rotated[:, 0]
    normals = np.cross(edges_a, edges_b)
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
    light = np.array([-0.35, 0.55, 0.76])
    light /= np.linalg.norm(light)
    light_levels = np.clip(normals @ light, 0, 1)
    depth_order = np.argsort(rotated[..., 2].mean(axis=1))

    for index in depth_order:
        if normals[index, 2] <= 1e-6:
            continue
        points = [tuple(point) for point in projected[index]]
        intensity = 0.38 + 0.72 * float(light_levels[index])
        draw.polygon(points, fill=shade(base_color, intensity))

    title_font = ImageFont.load_default(size=27 * scale_factor)
    detail_font = ImageFont.load_default(size=18 * scale_factor)
    size = mesh_size(triangles)
    title_y = 544 * scale_factor
    draw.text((width / 2, title_y), title, fill="#f5f6f7", font=title_font, anchor="ma")
    dimensions = f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm"
    draw.text(
        (width / 2, title_y + 39 * scale_factor),
        dimensions,
        fill="#c6cbd2",
        font=detail_font,
        anchor="ma",
    )
    draw.text(
        (width / 2, title_y + 68 * scale_factor),
        f"{len(triangles):,} triangles | closed mesh",
        fill="#8f98a3",
        font=detail_font,
        anchor="ma",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.resize((500, 650), Image.Resampling.LANCZOS).save(output_path, optimize=True)


def build_gallery(previews: list[Path], output_path: Path) -> None:
    gap = 24
    tile_width, tile_height = 500, 650
    gallery = Image.new(
        "RGB",
        (tile_width * len(previews) + gap * (len(previews) + 1), tile_height + gap * 2),
        "#0f1114",
    )
    for index, preview in enumerate(previews):
        tile = Image.open(preview).convert("RGB")
        gallery.paste(tile, (gap + index * (tile_width + gap), gap))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gallery.save(output_path, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "3d_enclosure")
    parser.add_argument("--output", type=Path, default=ROOT / "docs" / "images" / "enclosure")
    args = parser.parse_args()

    previews = []
    for filename, title, color in PARTS:
        source = args.input.resolve() / filename
        output = args.output.resolve() / f"{source.stem}.png"
        render_part(source, title, color, output)
        previews.append(output)
        print(output)

    gallery = args.output.resolve().parent / "enclosure-gallery.png"
    build_gallery(previews, gallery)
    print(gallery)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
