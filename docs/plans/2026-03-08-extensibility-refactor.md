# Extensibility Refactor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Decouple UI, domain logic, and persistence so new features can be added without editing multiple monolithic UI files.

**Architecture:** Keep PySide UI as a thin orchestration layer and move behavior into small testable services/modules. Preserve current JSON format compatibility while introducing typed normalization and domain helpers. Implement in small TDD increments with a green build after every task.

**Tech Stack:** Python 3, PySide6, `unittest`, existing JSON project format, existing UI modules (`ui/main_window.py`, `ui/editor_widget.py`, `ui/canvas_widget.py`).

---

**Required workflow skills during execution:** `@superpowers:test-driven-development`, `@superpowers:verification-before-completion`, `@superpowers:executing-plans`.

### Task 1: Introduce Typed Scale Reference Domain Object

**Files:**
- Create: `core/scale_reference.py`
- Create: `tests/test_scale_reference_domain.py`
- Modify: `ui/editor_widget.py`
- Modify: `ui/main_window.py`

**Step 1: Write the failing test**

```python
import unittest
from core.scale_reference import ScaleReference


class ScaleReferenceDomainTests(unittest.TestCase):
    def test_to_meters_for_meter_unit(self):
        self.assertAlmostEqual(ScaleReference(1.0, "m").to_meters(), 1.0)

    def test_to_meters_for_10cm_unit(self):
        self.assertAlmostEqual(ScaleReference(1.0, "cm10").to_meters(), 0.1)

    def test_to_meters_for_1cm_unit(self):
        self.assertAlmostEqual(ScaleReference(1.0, "cm1").to_meters(), 0.01)
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m unittest tests.test_scale_reference_domain -v`  
Expected: `FAIL/ERROR` because `core.scale_reference` does not exist yet.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleReference:
    length_value: float
    unit_key: str = "m"

    def normalize_unit(self) -> str:
        return self.unit_key if self.unit_key in {"m", "cm10", "cm1"} else "m"

    def to_meters(self) -> float:
        unit = self.normalize_unit()
        factors = {"m": 1.0, "cm10": 0.1, "cm1": 0.01}
        value = max(1e-6, float(self.length_value))
        return value * factors[unit]
```

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m unittest tests.test_scale_reference_domain -v`  
Expected: `OK`.

**Step 5: Commit**

```bash
git add core/scale_reference.py tests/test_scale_reference_domain.py ui/editor_widget.py ui/main_window.py
git commit -m "refactor: introduce scale reference domain helper"
```

### Task 2: Extract Project Settings Normalization from MainWindow

**Files:**
- Create: `core/project_settings.py`
- Create: `tests/test_project_settings.py`
- Modify: `ui/main_window.py`

**Step 1: Write the failing test**

```python
import unittest
from core.project_settings import normalize_project_settings


class ProjectSettingsTests(unittest.TestCase):
    def test_defaults_for_missing_fields(self):
        settings = normalize_project_settings({})
        self.assertEqual(settings["scale_reference_length"], 1.0)
        self.assertEqual(settings["scale_reference_unit"], "m")
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m unittest tests.test_project_settings -v`  
Expected: `FAIL/ERROR` because module/function is missing.

**Step 3: Write minimal implementation**

```python
def normalize_project_settings(data):
    out = dict(data or {})
    out["atlas_density"] = float(out.get("atlas_density", 512.0))
    out["atlas_size"] = int(out.get("atlas_size", 2048))
    out["scale_reference_length"] = max(0.01, float(out.get("scale_reference_length", 1.0)))
    unit = out.get("scale_reference_unit", "m")
    out["scale_reference_unit"] = unit if unit in {"m", "cm10", "cm1"} else "m"
    return out
```

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m unittest tests.test_project_settings -v`  
Expected: `OK`.

**Step 5: Commit**

```bash
git add core/project_settings.py tests/test_project_settings.py ui/main_window.py
git commit -m "refactor: move project settings normalization to core module"
```

### Task 3: Move Save/Load JSON Logic into Project Store Service

**Files:**
- Create: `core/project_store.py`
- Create: `tests/test_project_store.py`
- Modify: `ui/main_window.py`

**Step 1: Write the failing test**

```python
import unittest
from core.project_store import prepare_for_save, normalize_loaded_project


class ProjectStoreTests(unittest.TestCase):
    def test_prepare_for_save_writes_scale_reference_fields(self):
        data = {"textures": {}, "items": []}
        saved = prepare_for_save(data, scale_reference_length=0.5, scale_reference_unit="cm10")
        self.assertEqual(saved["scale_reference_length"], 0.5)
        self.assertEqual(saved["scale_reference_unit"], "cm10")

    def test_normalize_loaded_project_backfills_scale_reference_fields(self):
        loaded = normalize_loaded_project({"textures": {}, "items": []})
        self.assertEqual(loaded["scale_reference_length"], 1.0)
        self.assertEqual(loaded["scale_reference_unit"], "m")
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m unittest tests.test_project_store -v`  
Expected: `FAIL/ERROR` because service does not exist.

**Step 3: Write minimal implementation**

```python
from copy import deepcopy
from .project_settings import normalize_project_settings


def prepare_for_save(project_data, scale_reference_length, scale_reference_unit):
    out = deepcopy(project_data)
    out["scale_reference_length"] = max(0.01, float(scale_reference_length))
    out["scale_reference_unit"] = scale_reference_unit if scale_reference_unit in {"m", "cm10", "cm1"} else "m"
    return out


def normalize_loaded_project(project_data):
    out = deepcopy(project_data or {})
    out = normalize_project_settings(out)
    out.setdefault("textures", {})
    out.setdefault("items", [])
    return out
```

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m unittest tests.test_project_store -v`  
Expected: `OK`.

**Step 5: Commit**

```bash
git add core/project_store.py tests/test_project_store.py ui/main_window.py
git commit -m "refactor: extract project save/load logic into project store"
```

### Task 4: Extract Mask Upsert/Deletion Rules into Pure Service

**Files:**
- Create: `core/mask_service.py`
- Create: `tests/test_mask_service.py`
- Modify: `ui/main_window.py`

**Step 1: Write the failing test**

```python
import unittest
from core.mask_service import upsert_mask_entry, remove_mask_entry


class MaskServiceTests(unittest.TestCase):
    def test_upsert_updates_existing_mask(self):
        masks = [{"id": 1, "points": [(0, 0)], "real_width": 1.0, "original_width": 100.0, "color": "#ffffff"}]
        updated, mask_id = upsert_mask_entry(masks, mask_id=1, points=[(1, 1)], real_width=2.0, original_width=200.0)
        self.assertEqual(mask_id, 1)
        self.assertEqual(updated[0]["real_width"], 2.0)

    def test_remove_mask_entry(self):
        masks = [{"id": 1}, {"id": 2}]
        remaining = remove_mask_entry(masks, mask_id=1)
        self.assertEqual([m["id"] for m in remaining], [2])
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m unittest tests.test_mask_service -v`  
Expected: `FAIL/ERROR` due missing service.

**Step 3: Write minimal implementation**

```python
def upsert_mask_entry(masks, mask_id, points, real_width, original_width, color_factory=None):
    out = list(masks or [])
    for m in out:
        if m.get("id") == mask_id:
            m["points"] = points
            m["real_width"] = real_width
            m["original_width"] = original_width
            return out, mask_id
    next_id = max([m.get("id", 0) for m in out] + [0]) + 1
    out.append({
        "id": next_id,
        "points": points,
        "real_width": real_width,
        "original_width": original_width,
        "color": color_factory(next_id) if color_factory else None,
    })
    return out, next_id


def remove_mask_entry(masks, mask_id):
    return [m for m in (masks or []) if m.get("id") != mask_id]
```

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m unittest tests.test_mask_service -v`  
Expected: `OK`.

**Step 5: Commit**

```bash
git add core/mask_service.py tests/test_mask_service.py ui/main_window.py
git commit -m "refactor: move mask list mutations into pure service"
```

### Task 5: Slim Down EditorWidget Scale Flow and Remove Duplicated Logic

**Files:**
- Modify: `ui/editor_widget.py`
- Modify: `tests/test_scale_units.py`
- Modify: `tests/test_scale_reference_persistence.py`

**Step 1: Write the failing test**

```python
import unittest
from ui.editor_widget import EditorWidget


class EditorScaleFlowTests(unittest.TestCase):
    def test_scale_length_conversion_uses_domain_object(self):
        self.assertAlmostEqual(EditorWidget.scale_length_to_meters(1.0, "cm10"), 0.1)
```

**Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m unittest tests.test_scale_units -v`  
Expected: failure after removing duplicate conversion logic from widget.

**Step 3: Write minimal implementation**

```python
from core.scale_reference import ScaleReference


@staticmethod
def scale_length_to_meters(length_value, unit_key):
    return ScaleReference(length_value=length_value, unit_key=unit_key).to_meters()
```

**Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m unittest tests.test_scale_units tests.test_scale_reference_persistence -v`  
Expected: `OK`.

**Step 5: Commit**

```bash
git add ui/editor_widget.py tests/test_scale_units.py tests/test_scale_reference_persistence.py
git commit -m "refactor: centralize scale conversion behind domain object"
```

### Task 6: Final Verification and Documentation Update

**Files:**
- Modify: `README.md`
- Modify: `AGENT_NOTES.md`
- Modify: `docs/plans/2026-03-08-extensibility-refactor.md` (mark executed items when done)

**Step 1: Write the failing documentation check**

```text
Manual check list:
1) README must mention architecture split (UI vs core services)
2) AGENT_NOTES must list new core modules and responsibilities
```

**Step 2: Run verification command before docs update**

Run: `.venv\Scripts\python -m unittest discover -s tests -v`  
Expected: `OK` before editing docs.

**Step 3: Write minimal documentation updates**

```markdown
- Added core services: scale_reference, project_settings, project_store, mask_service
- MainWindow now orchestrates services instead of mutating project dict directly
```

**Step 4: Run full verification**

Run: `.venv\Scripts\python -m unittest discover -s tests -v`  
Expected: all tests pass.

**Step 5: Commit**

```bash
git add README.md AGENT_NOTES.md
git commit -m "docs: document refactored architecture and extension points"
```

### Definition of Done

1. `MainWindow` no longer contains primary normalization/mutation rules for project settings and masks.
2. Scale conversion logic has one source of truth in `core/scale_reference.py`.
3. Save/load JSON behavior remains backward-compatible for existing project files.
4. All tests pass with `unittest discover`.
5. Docs explain extension points for adding new units, settings, and mask rules.

### Execution Status (2026-03-08)

- [x] Task 1: Introduce Typed Scale Reference Domain Object
- [x] Task 2: Extract Project Settings Normalization from MainWindow
- [x] Task 3: Move Save/Load JSON Logic into Project Store Service
- [x] Task 4: Extract Mask Upsert/Deletion Rules into Pure Service
- [x] Task 5: Slim Down EditorWidget Scale Flow and Remove Duplicated Logic
- [x] Task 6: Final Verification and Documentation Update
