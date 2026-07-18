import numpy as np


def apply_rescale(arr, slope, intercept):
    if arr is None:
        return None
    try:
        slope = float(slope) if slope is not None else 1.0
        intercept = float(intercept) if intercept is not None else 0.0
        if not np.issubdtype(arr.dtype, np.floating):
            arr = arr.astype(np.float64)
        return arr * slope + intercept
    except Exception as e:
        print(f"Error applying rescale (slope={slope}, intercept={intercept}): {e}")
        if not np.issubdtype(arr.dtype, np.floating):
            return arr.astype(np.float64)
        return arr.copy()


def apply_window_level(arr, wc, ww, photometric_interpretation="MONOCHROME2"):
    if arr is None:
        return None
    if wc is None or ww is None:
        return normalize_image(arr, photometric_interpretation)
    try:
        wc = float(wc)
        ww = float(ww)
    except (TypeError, ValueError):
        return normalize_image(arr, photometric_interpretation)
    if ww < 1:
        ww = 1.0
    arr_float = arr.astype(np.float64, copy=False)
    lower_bound = wc - ww / 2.0
    upper_bound = wc + ww / 2.0
    scaled_arr = ((arr_float - lower_bound) / ww) * 255.0
    clipped_arr = np.clip(scaled_arr, 0, 255)
    if photometric_interpretation == 'MONOCHROME1':
        clipped_arr = 255.0 - clipped_arr
    return clipped_arr.astype(np.uint8)


def normalize_image(arr, photometric_interpretation="MONOCHROME2"):
    if arr is None:
        return None
    arr_float = arr.astype(np.float64, copy=True)
    min_val = np.min(arr_float)
    max_val = np.max(arr_float)
    if max_val == min_val:
        fill_value = 128
        if min_val <= 0:
            fill_value = 0
        elif min_val >= 255:
            fill_value = 255
        final_arr = np.full(arr_float.shape, fill_value, dtype=np.uint8)
    else:
        norm = (arr_float - min_val) / (max_val - min_val) * 255.0
        final_arr = np.clip(norm, 0, 255).astype(np.uint8)
    if photometric_interpretation == 'MONOCHROME1':
        final_arr = 255 - final_arr
    return final_arr


def apply_brightness_contrast(image_array_8bit, brightness=0, contrast=1.0, negative=False):
    if image_array_8bit is None:
        return None
    if image_array_8bit.dtype != np.uint8:
        image_array_8bit = normalize_image(image_array_8bit)
        if image_array_8bit is None:
            return None
    try:
        new_img = image_array_8bit.astype(np.float64)
        mean_val = 128.0
        new_img = mean_val + contrast * (new_img - mean_val)
        new_img += brightness
        new_img = np.clip(new_img, 0, 255)
        if negative:
            new_img = 255.0 - new_img
        return new_img.astype(np.uint8)
    except Exception as e:
        print(f"Error applying brightness/contrast: {e}")
        return None


def apply_lut(image_array_8bit, lut_table):
    if image_array_8bit is None or lut_table is None:
        return image_array_8bit
    try:
        if image_array_8bit.dtype != np.uint8:
            image_array_8bit = normalize_image(image_array_8bit)
        return lut_table[image_array_8bit]
    except Exception as e:
        print(f"Error applying LUT: {e}")
        return image_array_8bit
