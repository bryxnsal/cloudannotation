"""
AI Heuristic Cable Detector.
Segments overhead power lines and conductors via geometric linearity and elevation criteria.
"""
from typing import Tuple
import numpy as np
from sklearn.neighbors import NearestNeighbors

class CableDetector:
    """
    Detects overhead cables using PCA covariance linearity and aerial elevation thresholds.
    """
    @staticmethod
    def detect_cables(
        xyz: np.ndarray,
        min_clearance: float = 1.5
    ) -> Tuple[bool, str, np.ndarray]:
        """
        Segment linear cable points.
        Returns (success, message, local_cable_indices).
        """
        if len(xyz) < 5:
            return False, "Not enough points selected for cable analysis", np.array([], dtype=int)

        try:
            xy = xyz[:, :2]
            z_vals = xyz[:, 2]

            # 2.5D ground surface estimation in 1.5m cells
            cell_size = 1.5
            xy_min = np.min(xy, axis=0)
            gx = np.floor((xy[:, 0] - xy_min[0]) / cell_size).astype(int)
            gy = np.floor((xy[:, 1] - xy_min[1]) / cell_size).astype(int)
            cell_ids = gx + gy * 100000

            unique_cids = np.unique(cell_ids)
            z_ground_map = {cid: np.percentile(z_vals[cell_ids == cid], 8) for cid in unique_cids}
            z_ground_local = np.array([z_ground_map[cid] for cid in cell_ids])
            rel_height = z_vals - z_ground_local

            # Aerial clearance: only consider points elevated above local ground
            total_z_span = np.max(z_vals) - np.min(z_ground_local)
            if total_z_span >= 2.5:
                air_mask = rel_height >= min_clearance
            else:
                air_mask = np.ones(len(xyz), dtype=bool)

            air_indices = np.where(air_mask)[0]
            if len(air_indices) < 4:
                return False, "No points found suspended in the air within selection", np.array([], dtype=int)

            air_xyz = xyz[air_indices]
            n_air = len(air_xyz)

            k = min(8, n_air - 1)
            nbrs = NearestNeighbors(n_neighbors=k + 1, algorithm='kd_tree').fit(air_xyz)
            _, nn_indices = nbrs.kneighbors(air_xyz)

            is_cable = np.zeros(n_air, dtype=bool)
            for i in range(n_air):
                local_pts = air_xyz[nn_indices[i]]
                cov = np.cov(local_pts, rowvar=False)
                if cov.shape != (3, 3):
                    continue

                eigvals, eigvecs = np.linalg.eigh(cov)
                eigvals = np.maximum(eigvals, 1e-9)
                l1, l2, l3 = eigvals[0], eigvals[1], eigvals[2]

                linearity = (l3 - l2) / l3
                scattering = l1 / l3
                primary_dir = eigvecs[:, 2]
                verticality = abs(primary_dir[2])

                # Cables: Linear (>= 0.45), low 3D scattering (<= 0.12), not purely vertical (<= 0.80)
                if linearity >= 0.45 and scattering <= 0.12 and verticality <= 0.80:
                    is_cable[i] = True

            cable_air_idx = air_indices[is_cable]
            if len(cable_air_idx) == 0:
                return False, "No linear cable structures detected at elevated height", np.array([], dtype=int)

            return True, f"Detected {len(cable_air_idx)} cable points", cable_air_idx
        except Exception as e:
            return False, f"Cable analysis error: {str(e)}", np.array([], dtype=int)
