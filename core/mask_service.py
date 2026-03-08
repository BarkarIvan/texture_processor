from copy import deepcopy


def upsert_mask_entry(masks, mask_id, points, real_width, original_width, color_factory):
    out = deepcopy(masks or [])

    for m in out:
        if m.get("id") == mask_id:
            m["points"] = points
            m["real_width"] = real_width
            m["original_width"] = original_width
            if not m.get("color"):
                m["color"] = color_factory(mask_id)
            return out, mask_id

    next_id = max([m.get("id", 0) for m in out] + [0]) + 1
    out.append({
        "id": next_id,
        "points": points,
        "real_width": real_width,
        "original_width": original_width,
        "color": color_factory(next_id),
    })
    return out, next_id


def remove_mask_entry(masks, mask_id):
    return [deepcopy(m) for m in (masks or []) if m.get("id") != mask_id]
