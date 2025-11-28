from dataclasses import dataclass
from typing import Tuple

@dataclass
class AtlasItem:
    texture_path: str
    mask_index: int
    position: Tuple[float, float] = (0.0, 0.0)
    scale: float = 1.0
    rotation: float = 0.0 # Degrees
