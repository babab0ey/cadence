from dataclasses import dataclass, field
from typing import Optional, List, Any
import numpy as np


@dataclass
class ViewData:
    file_path: Optional[str] = None
    original_array: Optional[np.ndarray] = None
    rescaled_array: Optional[np.ndarray] = None
    base_8bit_array: Optional[np.ndarray] = None
    adjusted_array: Optional[np.ndarray] = None
    qimage: Any = None
    pixmap_item: Any = None
    pixel_spacing: float = 1.0
    rescale_slope: float = 1.0
    rescale_intercept: float = 0.0
    wc: Optional[float] = None
    ww: Optional[float] = None
    photometric_interpretation: str = 'MONOCHROME2'
    number_of_frames: int = 1
    current_frame_index: int = 0
    patient_name: str = 'N/A'
    patient_id: str = 'N/A'
    patient_birth_date: str = 'N/A'
    patient_sex: str = 'N/A'
    study_date: str = 'N/A'
    study_time: str = 'N/A'
    study_description: str = 'N/A'
    modality: str = 'N/A'
    institution_name: str = 'N/A'
    body_part: str = 'N/A'
    view_position: str = ''
    rotation: int = 0
    flip_h: bool = False
    flip_v: bool = False
    overlay_items: List = field(default_factory=list)
    file_type: str = 'unknown'
    series_description: str = ''
    manufacturer: str = 'N/A'
    equipment_model: str = 'N/A'
    station_name: str = 'N/A'

    def is_loaded(self) -> bool:
        return self.original_array is not None

    def has_pixmap(self) -> bool:
        return self.pixmap_item is not None
