"""Unit tests for the core remover engine."""

import io
import unittest
from PIL import Image, ImageDraw

from core.remover import (
    parse_color,
    load_and_normalize_image,
    composite_background,
    render_checkerboard_preview,
    export_image_bytes,
    remove_background,
    get_session,
)


class TestRemoverCore(unittest.TestCase):

    def test_parse_color(self):
        self.assertEqual(parse_color("#FFF"), (255, 255, 255, 255))
        self.assertEqual(parse_color("#000000"), (0, 0, 0, 255))
        self.assertEqual(parse_color("#FF000080"), (255, 0, 0, 128))
        self.assertEqual(parse_color((10, 20, 30)), (10, 20, 30, 255))
        self.assertEqual(parse_color((10, 20, 30, 100)), (10, 20, 30, 100))

        with self.assertRaises(ValueError):
            parse_color("invalid")

    def test_load_and_normalize_image(self):
        # Test RGB
        img_rgb = Image.new("RGB", (60, 60), color="blue")
        norm = load_and_normalize_image(img_rgb)
        self.assertEqual(norm.mode, "RGB")
        self.assertEqual(norm.size, (60, 60))

        # Test CMYK conversion to RGB
        img_cmyk = Image.new("CMYK", (40, 40), color=(0, 255, 255, 0))
        norm_cmyk = load_and_normalize_image(img_cmyk)
        self.assertEqual(norm_cmyk.mode, "RGB")

        # Test bytes input
        buf = io.BytesIO()
        img_rgb.save(buf, format="PNG")
        norm_bytes = load_and_normalize_image(buf.getvalue())
        self.assertEqual(norm_bytes.size, (60, 60))

    def test_composite_background(self):
        # Create a 50x50 transparent image with a 20x20 red square
        rgba_img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
        draw = ImageDraw.Draw(rgba_img)
        draw.rectangle([15, 15, 35, 35], fill=(255, 0, 0, 255))

        # Composite onto white background
        composited = composite_background(rgba_img, "#FFFFFF")
        self.assertEqual(composited.size, (50, 50))
        self.assertEqual(composited.mode, "RGB")

        # Corner should be white (255, 255, 255)
        self.assertEqual(composited.getpixel((0, 0)), (255, 255, 255))
        # Center should be red (255, 0, 0)
        self.assertEqual(composited.getpixel((25, 25)), (255, 0, 0))

    def test_export_image_bytes(self):
        rgba_img = Image.new("RGBA", (30, 30), (0, 255, 0, 128))

        # PNG export
        png_data, mime, ext = export_image_bytes(rgba_img, format="PNG")
        self.assertEqual(mime, "image/png")
        self.assertEqual(ext, ".png")
        self.assertTrue(len(png_data) > 0)

        # JPEG export (must not crash on RGBA)
        jpg_data, mime_jpg, ext_jpg = export_image_bytes(rgba_img, format="JPEG", bg_fill="#FFFFFF")
        self.assertEqual(mime_jpg, "image/jpeg")
        self.assertEqual(ext_jpg, ".jpg")
        self.assertTrue(len(jpg_data) > 0)

        # WEBP export
        webp_data, mime_webp, ext_webp = export_image_bytes(rgba_img, format="WEBP")
        self.assertEqual(mime_webp, "image/webp")
        self.assertEqual(ext_webp, ".webp")
        self.assertTrue(len(webp_data) > 0)

    def test_render_checkerboard_preview(self):
        rgba_img = Image.new("RGBA", (400, 200), (0, 0, 255, 100))
        preview = render_checkerboard_preview(rgba_img, max_size=(100, 100))

        # Check aspect ratio preservation: 400x200 should scale to (100, 50)
        self.assertEqual(preview.size, (100, 50))
        self.assertEqual(preview.mode, "RGBA")

    def test_end_to_end_removal(self):
        # Create a small image with a distinct subject
        img = Image.new("RGB", (80, 80), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        draw.ellipse([20, 20, 60, 60], fill=(20, 180, 30))

        session = get_session(force_cpu=True)
        out = remove_background(img, session=session)

        self.assertEqual(out.mode, "RGBA")
        self.assertEqual(out.size, (80, 80))


if __name__ == "__main__":
    unittest.main()
