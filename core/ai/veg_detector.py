"""
AI Heuristic Vegetation Detector.
Segments vegetation based on 3D volumetric scattering while preserving protected utility assets.
"""
from typing import Set, Tuple
import numpy as np
from sklearn.neighbors import NearestNeighbors

PROTECTED_CLASSES: Set[int] = {
    4, 6, 8,            # Postes BT, MT, AT
    5, 7, 9, 21, 22, 23 # Cables BT, MT, AT, MT 1, 2, 3
}

class VegetationDetector:
    """
    Detects foliage and trees using local covariance planarity, linearity, and 3D scattering.
    """
    @staticmethod
    def detect_vegetation(
        xyz: np.ndarray,
        current_classes: np.ndarray,
        min_clearance: float = 0.35,
        overwrite: bool = False
    ) -> Tuple[bool, str, np.ndarray]:
        """
        Segment vegetation points.
        Returns (success, message, local_veg_indices).
        """
        if len(xyz) < 10:
            return False, "Not enough points selected for vegetation analysis", np.array([], dtype=int)

        try:
            xy = xyz[:, :2]
            z_vals = xyz[:, 2]

            # 2.5D ground surface estimation in 1.0m cells
            cell_size = 1.0
            xy_min = np.min(xy, axis=0)
            gx = np.floor((xy[:, 0] - xy_min[0]) / cell_size).astype(int)
            gy = np.floor((xy[:, 1] - xy_min[1]) / cell_size).astype(int)
            cell_ids = gx + gy * 100000

            unique_cids = np.unique(cell_ids)
            z_ground_map = {cid: np.percentile(z_vals[cell_ids == cid], 8) for cid in unique_cids}
            z_ground_local = np.array([z_ground_map[cid] for cid in cell_ids])
            height_above_ground = z_vals - z_ground_local

            # Filter points above ground clearance
            total_z_span = np.max(z_vals) - np.min(z_ground_local)
            if total_z_span >= 1.5:
                above_ground_mask = height_above_ground >= min_clearance
            else:
                above_ground_mask = np.ones(len(xyz), dtype=bool)

            cand_indices = np.where(above_ground_mask)[0]
            if len(cand_indices) < 5:
                return False, "No elevated points found above ground level in selection", np.array([], dtype=int)

            cand_xyz = xyz[cand_indices]
            n_cand = len(cand_xyz)

            k = min(8, n_cand - 1)
            nbrs = NearestNeighbors(n_neighbors=k + 1, algorithm='kd_tree').fit(xyz)
            _, nn_indices = nbrs.kneighbors(cand_xyz)

            is_veg = np.zeros(n_cand, dtype=bool)
            for i in range(n_cand):
                orig_idx = cand_indices[i]
                orig_cls = current_classes[orig_idx]

                # Protect utility poles and conductors
                if orig_cls in PROTECTED_CLASSES:
                    continue

                if not overwrite and orig_cls > 0:
                    continue

                local_pts = xyz[nn_indices[i]]
                cov = np.cov(local_pts, rowvar=False)
                if cov.shape != (3, 3):
                    continue

                eigvals, eigvecs = np.linalg.eigh(cov)
                eigvals = np.maximum(eigvals, 1e-9)
                l1, l2, l3 = eigvals[0], eigvals[1], eigvals[2]

                linearity = (l3 - l2) / l3
                planarity = (l2 - l1) / l3
                scattering = l1 / l3
                primary_dir = eigvecs[:, 2]
                verticality = abs(primary_dir[2])

                is_cable = (linearity >= 0.60 and scattering <= 0.05 and verticality <= 0.40)
                is_pole = (verticality >= 0.70 and linearity >= 0.45)
                is_plane = (planarity >= 0.75 and scattering <= 0.04)

                if not is_cable and not is_pole and not is_plane:
                    is_veg[i] = True

            veg_local_idx = cand_indices[is_veg]
            if len(veg_local_idx) == 0:
                return False, "No vegetation patterns detected in selection", np.array([], dtype=int)

            return True, f"Detected {len(veg_local_idx)} vegetation points", veg_local_idx
        except Exception as e:
            return False, f"Vegetation analysis error: {str(e)}", np.array([], dtype=int)
