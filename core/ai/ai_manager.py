"""
AiManager: Orchestrates execution of AI detectors against point cloud selections and manages classification workflow.
"""
from typing import Tuple
import numpy as np
from Mask import Mask
from .ground_detector import GroundDetector
from .pole_detector import PoleDetector
from .cable_detector import CableDetector
from .veg_detector import VegetationDetector


class AiManager:
    """
    Coordinates AI classification passes with point cloud selection and classification.
    """

    @staticmethod
    def _extract_target_points(point_cloud) -> Tuple[bool, str, np.ndarray, np.ndarray]:
        if not point_cloud.viewer_is_ready():
            return False, "Viewer is not ready", None, None
        if not point_cloud.has_selection() and not point_cloud.is_work_area_active():
            return False, "Select a region or isolate a work area first", None, None

        mask = point_cloud.get_highlighted_mask() if point_cloud.has_selection() else Mask(len(point_cloud.points), False)
        if not point_cloud.has_selection():
            mask.bools = point_cloud.active_roi.bools.copy()

        pts_indices = np.where(mask.bools)[0]
        xyz = point_cloud.points.loc[pts_indices, ['x', 'y', 'z']].values
        return True, "", pts_indices, xyz

    @staticmethod
    def auto_ground(point_cloud, cell_size: float = 1.0, distance_threshold: float = 0.25, overwrite: bool = False) -> Tuple[bool, str]:
        ok, msg, pts_indices, xyz = AiManager._extract_target_points(point_cloud)
        if not ok:
            return False, msg

        success, det_msg, local_indices = GroundDetector.detect_ground(
            xyz, cell_size=cell_size, distance_threshold=distance_threshold
        )
        if not success:
            return False, det_msg

        ground_global = pts_indices[local_indices]
        mask = Mask(len(point_cloud.points), False)
        mask.bools[ground_global] = True
        point_cloud.classify(cls=1, mask=mask, overwrite=overwrite, preserve_camera=True)
        return True, f"Auto Ground: Classified {len(ground_global)}/{len(pts_indices)} points as Suelo"

    @staticmethod
    def classify_pole(point_cloud, height_threshold: float = 12.0, cylinder_radius: float = 0.55, overwrite: bool = False) -> Tuple[bool, str]:
        ok, msg, pts_indices, xyz = AiManager._extract_target_points(point_cloud)
        if not ok:
            return False, msg

        success, det_msg, local_indices, cls_code, height = PoleDetector.detect_pole(
            xyz, height_threshold=height_threshold, cylinder_radius=cylinder_radius
        )
        if not success:
            return False, det_msg

        pole_global = pts_indices[local_indices]
        mask = Mask(len(point_cloud.points), False)
        mask.bools[pole_global] = True
        point_cloud.classify(cls=cls_code, mask=mask, overwrite=overwrite, preserve_camera=True)
        cls_name = "Postes MT" if cls_code == 6 else "Postes BT"
        return True, f"Classify Pole: {cls_name} (Height: {height:.2f}m, Isolated {len(pole_global)}/{len(pts_indices)} pts)"

    @staticmethod
    def grow_cable(point_cloud, min_clearance: float = 1.5, overwrite: bool = False) -> Tuple[bool, str]:
        ok, msg, pts_indices, xyz = AiManager._extract_target_points(point_cloud)
        if not ok:
            return False, msg

        success, det_msg, local_indices = CableDetector.detect_cables(
            xyz, min_clearance=min_clearance
        )
        if not success:
            return False, det_msg

        cable_global = pts_indices[local_indices]
        mask = Mask(len(point_cloud.points), False)
        mask.bools[cable_global] = True
        point_cloud.classify(cls=5, mask=mask, overwrite=overwrite, preserve_camera=True)
        return True, f"Grow Cable: Classified {len(cable_global)}/{len(pts_indices)} points as Cables BT"

    @staticmethod
    def classify_veg(point_cloud, min_clearance: float = 0.35, overwrite: bool = False) -> Tuple[bool, str]:
        ok, msg, pts_indices, xyz = AiManager._extract_target_points(point_cloud)
        if not ok:
            return False, msg

        current_classes = point_cloud.points.loc[pts_indices, 'class'].values
        success, det_msg, local_indices = VegetationDetector.detect_vegetation(
            xyz, current_classes=current_classes, min_clearance=min_clearance, overwrite=overwrite
        )
        if not success:
            return False, det_msg

        veg_global = pts_indices[local_indices]
        mask = Mask(len(point_cloud.points), False)
        mask.bools[veg_global] = True
        point_cloud.classify(cls=2, mask=mask, overwrite=overwrite, preserve_camera=True)
        return True, f"Classify Veg: Classified {len(veg_global)}/{len(pts_indices)} points as Vegetación"
