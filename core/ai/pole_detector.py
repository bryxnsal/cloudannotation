"""
AI Heuristic Pole Detector.
Segments vertical pole points using cylindrical neighborhood voting and height analysis.
"""
from typing import Tuple
import numpy as np
from sklearn.neighbors import NearestNeighbors

class PoleDetector:
    """
    Detects vertical poles and distinguishes between BT (low voltage) and MT (medium voltage).
    """
    @staticmethod
    def detect_pole(
        xyz: np.ndarray,
        height_threshold: float = 12.0,
        cylinder_radius: float = 0.55
    ) -> Tuple[bool, str, np.ndarray, int, float]:
        """
        Segment vertical pole points.
        Returns (success, message, local_pole_indices, class_code, pole_height).
        """
        if len(xyz) < 8:
            return False, "Not enough points selected for pole analysis", np.array([], dtype=int), 0, 0.0

        try:
            z_vals = xyz[:, 2]
            z_min, z_max = np.min(z_vals), np.max(z_vals)
            total_height = z_max - z_min
            if total_height < 1.5:
                return False, f"Selected object height ({total_height:.2f}m) is too short for a pole", np.array([], dtype=int), 0, 0.0

            xy = xyz[:, :2]
            n_pts = len(xyz)

            # Subsample candidates to evaluate centers if selection is huge
            if n_pts > 2000:
                sample_idx = np.random.choice(n_pts, size=2000, replace=False)
            else:
                sample_idx = np.arange(n_pts)

            cand_xy = xy[sample_idx]

            nbrs_2d = NearestNeighbors(radius=cylinder_radius, algorithm='kd_tree').fit(xy)
            indices_list = nbrs_2d.radius_neighbors(cand_xy, return_distance=False)

            best_score = -1.0
            best_center = None
            best_indices = None

            for i, in_radius_idx in enumerate(indices_list):
                if len(in_radius_idx) < 5:
                    continue
                z_subset = z_vals[in_radius_idx]
                span_z = np.max(z_subset) - np.min(z_subset)
                if span_z < 1.5:
                    continue

                # Continuous vertical span score
                score = span_z * np.log1p(len(in_radius_idx))
                if score > best_score:
                    best_score = score
                    best_center = cand_xy[i]
                    best_indices = in_radius_idx

            if best_center is None or len(best_indices) < 5:
                return False, "Could not find a prominent vertical pole axis in selection", np.array([], dtype=int), 0, 0.0

            # Refine pole axis center using median of candidate points
            center_x = np.median(xy[best_indices, 0])
            center_y = np.median(xy[best_indices, 1])

            # Horizontal distance from refined center
            dists = np.sqrt((xy[:, 0] - center_x) ** 2 + (xy[:, 1] - center_y) ** 2)
            pole_local_mask = dists <= cylinder_radius

            # Exclude flat ground points at the very base
            z_surrounding_ground = np.percentile(z_vals[dists > cylinder_radius], 5) if np.sum(dists > cylinder_radius) >= 10 else np.min(z_vals)
            pole_local_mask = pole_local_mask & (z_vals >= (z_surrounding_ground + 0.15))

            pole_local_indices = np.where(pole_local_mask)[0]
            if len(pole_local_indices) < 5:
                return False, "Could not isolate enough pole points", np.array([], dtype=int), 0, 0.0

            pole_z = z_vals[pole_local_indices]
            pole_height = float(np.max(pole_z) - np.min(pole_z))

            cls_code = 6 if pole_height > height_threshold else 4
            cls_name = "Postes MT" if cls_code == 6 else "Postes BT"

            return True, f"{cls_name} (Height: {pole_height:.2f}m)", pole_local_indices, cls_code, pole_height
        except Exception as e:
            return False, f"Pole detection error: {str(e)}", np.array([], dtype=int), 0, 0.0
