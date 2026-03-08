from copy import deepcopy

from core.project_settings import normalize_project_settings


def prepare_for_save(project_data, scale_reference_length, scale_reference_unit):
    out = deepcopy(project_data or {})
    out["scale_reference_length"] = scale_reference_length
    out["scale_reference_unit"] = scale_reference_unit
    out = normalize_project_settings(out)
    out.setdefault("textures", {})
    out.setdefault("items", [])
    return out


def normalize_loaded_project(project_data):
    out = deepcopy(project_data or {})
    out = normalize_project_settings(out)
    out.setdefault("textures", {})
    out.setdefault("items", [])
    return out
