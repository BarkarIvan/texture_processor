import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any
from .texture import Texture, Mask
from .atlas import AtlasItem

@dataclass
class Project:
    name: str = "New Project"
    base_path: str = ""
    atlas_width: int = 2048
    atlas_height: int = 2048
    atlas_density: float = 512.0 # px/m
    textures: List[Texture] = field(default_factory=list)
    atlas_items: List[AtlasItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        # Manually reconstruct nested objects
        textures_data = data.get('textures', [])
        textures = []
        for t_data in textures_data:
            masks_data = t_data.get('masks', [])
            masks = [Mask(**m) for m in masks_data]
            t_data['masks'] = masks
            textures.append(Texture(**t_data))
        
        atlas_items_data = data.get('atlas_items', [])
        atlas_items = [AtlasItem(**item) for item in atlas_items_data]
        
        data['textures'] = textures
        data['atlas_items'] = atlas_items
        return cls(**data)

    def save(self, filepath: str):
        data = self.to_dict()
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    @classmethod
    def load(cls, filepath: str) -> 'Project':
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data)
