import unittest

import numpy as np

from core.image_processor import (
    apply_brightness_contrast,
    apply_rescale_window,
    downsample_array,
)


class ImageProcessorTests(unittest.TestCase):
    def test_pipeline_uses_uint8_output_and_matches_window_formula(self):
        source = np.arange(48, dtype=np.uint16).reshape(6, 8)

        result = apply_rescale_window(
            source,
            slope=2.0,
            intercept=-10.0,
            wc=20.0,
            ww=40.0,
            chunk_rows=2,
        )

        expected = np.clip(((source.astype(np.float32) * 2.0 - 10.0) / 40.0) * 255.0, 0, 255)
        np.testing.assert_array_equal(result, expected.astype(np.uint8))
        self.assertEqual(result.dtype, np.uint8)

    def test_identity_adjustment_reuses_existing_display_buffer(self):
        display = np.arange(25, dtype=np.uint8).reshape(5, 5)

        result = apply_brightness_contrast(display)

        self.assertIs(result, display)

    def test_monochrome1_is_inverted(self):
        source = np.array([[0, 100]], dtype=np.uint16)

        normal = apply_rescale_window(source, wc=50, ww=100)
        inverted = apply_rescale_window(
            source,
            wc=50,
            ww=100,
            photometric_interpretation="MONOCHROME1",
        )

        np.testing.assert_array_equal(inverted, 255 - normal)

    def test_downsampling_bounds_both_dimensions(self):
        source = np.zeros((4096, 3328), dtype=np.uint16)

        preview = downsample_array(source, max_size=168)

        self.assertLessEqual(preview.shape[0], 168)
        self.assertLessEqual(preview.shape[1], 168)
        self.assertTrue(preview.flags.c_contiguous)
        self.assertLess(preview.nbytes, 168 * 168 * source.itemsize)


if __name__ == "__main__":
    unittest.main()
