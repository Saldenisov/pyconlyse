"""Concentric-contour symmetry measurements for laser-beam alignment."""

import numpy as np

try:
    import cv2
except ImportError:  # Keep the controller available for manual operation.
    cv2 = None


def _grayscale_camera_image(image, width=None, height=None):
    """Return a 2-D image from Basler's vertically stacked RGB transfer."""

    array = np.asarray(image)
    if array.size == 0:
        raise ValueError("camera image is empty")
    expected_width = int(width) if width is not None else None
    expected_height = int(height) if height is not None else None
    if array.ndim == 1:
        if not expected_width or not expected_height:
            raise ValueError("flat camera image requires width and height")
        if array.size == expected_width * expected_height * 3:
            array = array.reshape(3, expected_height, expected_width).transpose(1, 2, 0)
        elif array.size == expected_width * expected_height:
            array = array.reshape(expected_height, expected_width)
        else:
            raise ValueError("camera image size does not match width and height")
    elif (array.ndim == 2 and expected_width and expected_height
          and array.shape == (expected_height * 3, expected_width)):
        array = array.reshape(3, expected_height, expected_width).transpose(1, 2, 0)
    if array.ndim == 2:
        return array.astype(float, copy=False)
    if array.ndim != 3:
        raise ValueError(f"unsupported camera image shape {array.shape}")
    if array.shape[-1] in (3, 4):
        return array[..., :3].astype(float, copy=False).mean(axis=2)
    if array.shape[0] in (3, 4):
        return array[:3].astype(float, copy=False).mean(axis=0)
    raise ValueError(f"unsupported colour camera image shape {array.shape}")


def _fitted_contour(contour):
    """Fit a subpixel circle and ellipse to one iso-intensity border."""

    points = contour.reshape(-1, 2).astype(float)
    if len(points) < 12:
        return None
    x, y = points.T
    matrix = np.column_stack((2.0 * x, 2.0 * y, np.ones(len(points))))
    centre_x, centre_y, _constant = np.linalg.lstsq(
        matrix, x * x + y * y, rcond=None
    )[0]
    radii = np.hypot(x - centre_x, y - centre_y)
    radius = float(np.mean(radii))
    if radius < 3.0:
        return None
    ellipse = cv2.fitEllipse(contour)
    minor_axis, major_axis = sorted(float(axis) for axis in ellipse[1])
    if major_axis <= 0:
        return None
    axis_ratio = minor_axis / major_axis
    return {
        "centre": [float(centre_x), float(centre_y)],
        "radius_px": radius,
        "axis_roundness_pct": 100.0 * axis_ratio,
        "ellipticity_error_pct": 100.0 * (1.0 - axis_ratio),
        "radial_error_pct": 100.0 * float(np.std(radii)) / radius,
        "major_axis_angle_deg": float(ellipse[2]),
    }


def beam_contour_symmetry(images, threshold, width=None, height=None):
    """Score a few frames by sweeping beam contours from outer ring to core.

    No term uses the absolute location of the beam in the camera frame.
    """

    if cv2 is None:
        raise ValueError("OpenCV is required for beam-contour alignment")
    frames = [_grayscale_camera_image(frame, width=width, height=height)
              for frame in images]
    if not frames or any(frame.shape != frames[0].shape for frame in frames):
        raise ValueError("camera frames are missing or have inconsistent sizes")
    gray = np.median(np.stack(frames), axis=0)
    if not np.isfinite(gray).all():
        raise ValueError("camera frame contains non-finite intensities")
    if min(gray.shape) < 12:
        raise ValueError("camera image is too small for contour analysis")

    smoothed = cv2.GaussianBlur(gray.astype(np.float32), (3, 3), 0)
    border = np.concatenate(
        (smoothed[0], smoothed[-1], smoothed[:, 0], smoothed[:, -1])
    )
    background = float(np.median(border))
    noise = float(np.median(np.abs(border - background))) * 1.4826
    peak = float(np.max(smoothed))
    floor = max(float(threshold), background + max(3.0, 4.0 * noise))
    if peak <= floor + 8.0:
        raise ValueError("beam is below the contour threshold")

    peak_y, peak_x = np.unravel_index(int(np.argmax(smoothed)), smoothed.shape)
    levels = []
    clipped_contours = False
    for fraction in (0.10, 0.16, 0.23, 0.31, 0.40, 0.50, 0.61, 0.72, 0.82):
        level = floor + fraction * (peak - floor)
        binary = np.uint8(smoothed >= level)
        contours, _hierarchy = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        selected = [contour for contour in contours
                    if cv2.pointPolygonTest(
                        contour, (float(peak_x), float(peak_y)), False
                    ) >= 0]
        if not selected:
            continue
        contour = max(selected, key=cv2.contourArea)
        x, y, contour_width, contour_height = cv2.boundingRect(contour)
        if (x <= 0 or y <= 0 or x + contour_width >= gray.shape[1]
                or y + contour_height >= gray.shape[0]):
            clipped_contours = True
            continue
        if cv2.contourArea(contour) < 25.0:
            continue
        fit = _fitted_contour(contour)
        if fit is None:
            continue
        fit["threshold"] = float(level)
        fit["relative_height"] = fraction
        levels.append(fit)

    if clipped_contours:
        raise ValueError("beam contours are clipped by the camera frame")
    if len(levels) < 3:
        raise ValueError("too few complete beam contours for symmetry analysis")
    centres = np.array([level["centre"] for level in levels])
    common_centre = np.median(centres, axis=0)
    outer_radius = max(level["radius_px"] for level in levels)
    centre_drift_px = float(np.sqrt(np.mean(np.sum(
        (centres - common_centre) ** 2, axis=1
    ))))
    centre_drift_pct = 100.0 * centre_drift_px / outer_radius
    ellipticity = float(np.mean([
        level["ellipticity_error_pct"] for level in levels
    ]))
    radial_error = float(np.mean([
        level["radial_error_pct"] for level in levels
    ]))
    error = min(100.0, 0.55 * ellipticity + 0.25 * radial_error
                + 0.20 * centre_drift_pct)
    axis_roundness = float(np.mean([
        level["axis_roundness_pct"] for level in levels
    ]))
    return {
        "roundness_pct": 100.0 - error,
        "roundness_error_pct": error,
        "axis_roundness_pct": axis_roundness,
        "ellipticity_error_pct": ellipticity,
        "radial_error_pct": radial_error,
        "asymmetry": centre_drift_px / outer_radius,
        "asymmetry_error_pct": centre_drift_pct,
        "contour_centre_drift_px": centre_drift_px,
        "contour_centre_drift_pct": centre_drift_pct,
        "shape_centroid": [float(common_centre[0]), float(common_centre[1])],
        "sigma_minor_px": float(min(level["radius_px"] for level in levels)),
        "sigma_major_px": outer_radius,
        "major_axis_angle_deg": float(levels[0]["major_axis_angle_deg"]),
        "illuminated_pixels": int(np.count_nonzero(smoothed >= floor)),
        "contour_count": len(levels),
        "contours": levels,
        "sample_count": len(frames),
    }


def beam_roundness(image, threshold, width=None, height=None):
    """Single-frame compatibility entry point."""

    return beam_contour_symmetry(
        [image], threshold=threshold, width=width, height=height
    )
