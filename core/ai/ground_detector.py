"""
AI Heuristic Ground Surface Detector.
Fits a 2.5D elevation grid to detect sloped or uneven ground terrain.
"""
from typing import Tuple
import numpy as np

class GroundDetector:
    """
    Detects ground plane across points using cell-based 2.5D elevation filtering.
    """
    @staticmethod
    def detect_ground(
        xyz: np.ndarray,
        cell_size: float = 1.0,
        distance_threshold: float = 0.25
    ) -> Tuple[bool, str, np.ndarray]:
        """
        Detect ground points.
        Returns (success, message, local_ground_indices).
        """
        if len(xyz) < 20:
            return False, "Not enough points selected for ground detection", np.array([], dtype=int)

        try:
            xy = xyz[:, :2]
            z = xyz[:, 2]

            # 2.5D cell-based ground elevation estimation
            xy_min = np.min(xy, axis=0)
            gx = np.floor((xy[:, 0] - xy_min[0]) / cell_size).astype(int)
            gy = np.floor((xy[:, 1] - xy_min[1]) / cell_size).astype(int)
            cell_ids = gx + gy * 100000

            unique_cids = np.unique(cell_ids)
            z_ground_map = {cid: np.percentile(z[cell_ids == cid], 8) for cid in unique_cids}

            z_ground_local = np.array([z_ground_map[cid] for cid in cell_ids])
            height_above_ground = z - z_ground_local

            ground_local = np.where(height_above_ground <= distance_threshold)[0]
            if len(ground_local) == 0:
                return False, "No ground points detected", np.array([], dtype=int)

            return True, f"Detected {len(ground_local)} ground points", ground_local
        except Exception as e:
            return False, f"Ground detection error: {str(e)}", np.array([], dtype=int)
