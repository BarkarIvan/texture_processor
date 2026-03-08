from copy import deepcopy

from core.scale_reference import ScaleReference


def _safe_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def normalize_project_settings(data):
    out = deepcopy(data or {})

    out["atlas_density"] = _safe_float(out.get("atlas_density", 512.0), 512.0)
    out["atlas_size"] = _safe_int(out.get("atlas_size", 2048), 2048)

    raw_len = _safe_float(out.get("scale_reference_length", 1.0), 1.0)
    out["scale_reference_length"] = max(0.01, raw_len)

    unit = out.get("scale_reference_unit", "m")
    out["scale_reference_unit"] = unit if unit in ScaleReference.allowed_units() else "m"

    return out
