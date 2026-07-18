import numpy as np


DEFAULT_CHUNK_ROWS = 256


def _iter_row_slices(array, chunk_rows=DEFAULT_CHUNK_ROWS):
    rows = array.shape[0] if array.ndim else 1
    for start in range(0, rows, max(1, int(chunk_rows))):
        yield slice(start, min(rows, start + chunk_rows))


def _finite_min_max(array):
    if array is None or array.size == 0:
        return 0.0, 0.0
    if np.issubdtype(array.dtype, np.floating):
        minimum = None
        maximum = None
        for row_slice in _iter_row_slices(array):
            chunk = array[row_slice]
            finite = np.isfinite(chunk)
            if finite.any():
                chunk_min = float(np.min(chunk, where=finite, initial=np.inf))
                chunk_max = float(np.max(chunk, where=finite, initial=-np.inf))
                minimum = chunk_min if minimum is None else min(minimum, chunk_min)
                maximum = chunk_max if maximum is None else max(maximum, chunk_max)
            del finite
        if minimum is None or maximum is None:
            return 0.0, 0.0
        return minimum, maximum
    return float(np.min(array)), float(np.max(array))


def apply_rescale(arr, slope, intercept):
    """Compatibility helper that uses float32 instead of retaining float64 data."""
    if arr is None:
        return None
    slope = float(slope) if slope is not None else 1.0
    intercept = float(intercept) if intercept is not None else 0.0
    result = np.array(arr, dtype=np.float32, copy=True)
    if slope != 1.0:
        np.multiply(result, np.float32(slope), out=result)
    if intercept != 0.0:
        np.add(result, np.float32(intercept), out=result)
    return result


def apply_window_level(
    arr,
    wc,
    ww,
    photometric_interpretation="MONOCHROME2",
    out=None,
    chunk_rows=DEFAULT_CHUNK_ROWS,
):
    if arr is None:
        return None
    if wc is None or ww is None:
        return normalize_image(arr, photometric_interpretation, out=out, chunk_rows=chunk_rows)
    try:
        wc = float(wc)
        ww = max(1.0, float(ww))
    except (TypeError, ValueError):
        return normalize_image(arr, photometric_interpretation, out=out, chunk_rows=chunk_rows)

    output = _prepare_output(arr, out)
    lower_bound = np.float32(wc - ww / 2.0)
    scale = np.float32(255.0 / ww)
    for row_slice in _iter_row_slices(arr, chunk_rows):
        chunk = np.array(arr[row_slice], dtype=np.float32, copy=True)
        np.subtract(chunk, lower_bound, out=chunk)
        np.multiply(chunk, scale, out=chunk)
        np.clip(chunk, 0.0, 255.0, out=chunk)
        output[row_slice] = chunk.astype(np.uint8)
        del chunk

    if photometric_interpretation == "MONOCHROME1":
        np.subtract(255, output, out=output)
    return output


def normalize_image(
    arr,
    photometric_interpretation="MONOCHROME2",
    out=None,
    chunk_rows=DEFAULT_CHUNK_ROWS,
):
    if arr is None:
        return None
    output = _prepare_output(arr, out)
    min_val, max_val = _finite_min_max(arr)
    if max_val == min_val:
        fill_value = 128
        if min_val <= 0:
            fill_value = 0
        elif min_val >= 255:
            fill_value = 255
        output.fill(fill_value)
    else:
        scale = np.float32(255.0 / (max_val - min_val))
        offset = np.float32(min_val)
        for row_slice in _iter_row_slices(arr, chunk_rows):
            chunk = np.array(arr[row_slice], dtype=np.float32, copy=True)
            np.subtract(chunk, offset, out=chunk)
            np.multiply(chunk, scale, out=chunk)
            np.clip(chunk, 0.0, 255.0, out=chunk)
            output[row_slice] = chunk.astype(np.uint8)
            del chunk

    if photometric_interpretation == "MONOCHROME1":
        np.subtract(255, output, out=output)
    return output


def apply_rescale_window(
    arr,
    slope=1.0,
    intercept=0.0,
    wc=None,
    ww=None,
    photometric_interpretation="MONOCHROME2",
    out=None,
    chunk_rows=DEFAULT_CHUNK_ROWS,
):
    """Create an 8-bit display buffer without a full-frame float intermediate."""
    if arr is None:
        return None
    slope = float(slope) if slope is not None else 1.0
    intercept = float(intercept) if intercept is not None else 0.0
    output = _prepare_output(arr, out)

    if wc is not None and ww is not None:
        try:
            wc_value = float(wc)
            ww_value = max(1.0, float(ww))
        except (TypeError, ValueError):
            wc_value = None
            ww_value = None
    else:
        wc_value = None
        ww_value = None

    if wc_value is None or ww_value is None:
        raw_min, raw_max = _finite_min_max(arr)
        value_a = raw_min * slope + intercept
        value_b = raw_max * slope + intercept
        lower = min(value_a, value_b)
        upper = max(value_a, value_b)
    else:
        lower = wc_value - ww_value / 2.0
        upper = lower + ww_value

    if upper == lower:
        fill_value = 0 if upper <= 0 else 255 if lower >= 255 else 128
        output.fill(fill_value)
    else:
        scale = np.float32(255.0 / (upper - lower))
        lower_value = np.float32(lower)
        slope_value = np.float32(slope)
        intercept_value = np.float32(intercept)
        for row_slice in _iter_row_slices(arr, chunk_rows):
            chunk = np.array(arr[row_slice], dtype=np.float32, copy=True)
            if slope != 1.0:
                np.multiply(chunk, slope_value, out=chunk)
            if intercept != 0.0:
                np.add(chunk, intercept_value, out=chunk)
            np.subtract(chunk, lower_value, out=chunk)
            np.multiply(chunk, scale, out=chunk)
            np.nan_to_num(chunk, copy=False, nan=0.0, posinf=255.0, neginf=0.0)
            np.clip(chunk, 0.0, 255.0, out=chunk)
            output[row_slice] = chunk.astype(np.uint8)
            del chunk

    if photometric_interpretation == "MONOCHROME1":
        np.subtract(255, output, out=output)
    return output


def apply_brightness_contrast(
    image_array_8bit,
    brightness=0,
    contrast=1.0,
    negative=False,
    out=None,
    chunk_rows=DEFAULT_CHUNK_ROWS,
):
    if image_array_8bit is None:
        return None
    if image_array_8bit.dtype != np.uint8:
        image_array_8bit = normalize_image(image_array_8bit)
        if image_array_8bit is None:
            return None

    brightness = float(brightness)
    contrast = float(contrast)
    if brightness == 0.0 and contrast == 1.0 and not negative and out is None:
        return image_array_8bit

    output = _prepare_output(image_array_8bit, out)
    contrast_value = np.float32(contrast)
    brightness_value = np.float32(brightness)
    for row_slice in _iter_row_slices(image_array_8bit, chunk_rows):
        chunk = np.array(image_array_8bit[row_slice], dtype=np.float32, copy=True)
        np.subtract(chunk, np.float32(128.0), out=chunk)
        np.multiply(chunk, contrast_value, out=chunk)
        np.add(chunk, np.float32(128.0) + brightness_value, out=chunk)
        np.clip(chunk, 0.0, 255.0, out=chunk)
        if negative:
            np.subtract(255.0, chunk, out=chunk)
        output[row_slice] = chunk.astype(np.uint8)
        del chunk
    return output


def apply_lut(image_array_8bit, lut_table):
    if image_array_8bit is None or lut_table is None:
        return image_array_8bit
    if image_array_8bit.dtype != np.uint8:
        image_array_8bit = normalize_image(image_array_8bit)
    return lut_table[image_array_8bit]


def downsample_array(array, max_size=168):
    """Return a small contiguous preview buffer using cheap stride sampling."""
    if array is None or array.size == 0 or array.ndim < 2:
        return None
    height, width = array.shape[:2]
    step = max(1, int(np.ceil(max(height, width) / max(1, int(max_size)))))
    if array.ndim == 2:
        sampled = array[::step, ::step]
    else:
        sampled = array[::step, ::step, ...]
    return np.ascontiguousarray(sampled)


def _prepare_output(array, out):
    if out is not None and out.shape == array.shape and out.dtype == np.uint8:
        return out
    return np.empty(array.shape, dtype=np.uint8)
