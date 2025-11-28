from dataclasses import dataclass, field
from typing import List, Tuple, Optional

@dataclass
class Mask:
    points: List[Tuple[float, float]] = field(default_factory=list) # (x, y) relative to image

@dataclass
class Texture:
    filepath: str
    real_width_meters: float = 1.0 # Default value
    masks: List[Mask] = field(default_factory=list)
    status: str = "no_mask" # no_mask, mask_created, used
