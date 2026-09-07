"""
Geometric, density, and feature extraction filters.
"""
from collections import defaultdict
import numpy as np
from tqdm import tqdm
import pptk
import knn as knn
from Voxelize import VoxelGrid

class PointCloudFilters:
    """
    Filtering algorithms: rounding, radial, planar, regularization, normals, curvature, Hough transforms.
    """
    @staticmethod
    def slice(points_xyz: np.ndarray, position: float = 1.75, thickness: float = 0.2, axis: int = 2) -> np.ndarray:
        """
        Take an axis-aligned planar slice of thickness from points.
        axis: 0 for x, 1 for y, 2 for z.
        """
        coord = points_xyz[:, axis]
        mask = (coord > position) & (coord <= position + thickness)
        return mask

    @staticmethod
    def rounding_filter(points_xyz: np.ndarray, round_val: float = 0.02) -> np.ndarray:
        """
        Round point locations to nearest round_val and return unique coordinates.
        """
        return np.unique(np.round(points_xyz / round_val, decimals=0) * round_val, axis=0)

    @staticmethod
    def radial_filter(points_xyz: np.ndarray, threshold: int = 10, radius: float = 0.05) -> np.ndarray:
        """
        Verify each point has at least threshold neighbors within radius.
        """
        query = knn.Query()
        query.pptk(points_xyz)
        keep = np.ones(len(points_xyz), dtype=bool)
        for i, p in enumerate(tqdm(points_xyz, desc='Finding neighbors and filtering')):
            neighbors = query.neighbors(p, k=threshold, radius=radius)
            if len(neighbors) < threshold:
                keep[i] = False
        return keep

    @staticmethod
    def plane_filter(points_xyz: np.ndarray, mesh: float = 0.06, axis: int = 2) -> np.ndarray:
        """
        Counts of points in each slice of the point cloud segmented in the given axis.
        """
        mesh_vec = np.ones(3) * mesh
        if axis == 0:
            mesh_vec[[1, 2]] = 10000000.0
        elif axis == 1:
            mesh_vec[[0, 2]] = 10000000.0
        elif axis == 2:
            mesh_vec[[0, 1]] = 10000000.0

        vg = VoxelGrid(points_xyz, mesh_vec)
        return np.array([vg.counts(vg.index(p)) for p in points_xyz])

    @staticmethod
    def regularize(points_xyz: np.ndarray, mesh: float = 0.02) -> np.ndarray:
        """
        Downsample point cloud to 1 point per voxel grid of mesh size.
        """
        vg = VoxelGrid(points_xyz, mesh_size=mesh)
        keep = np.zeros(len(points_xyz), dtype=bool)
        for indices in vg.indices():
            keep[indices[0]] = True
        return keep

    @staticmethod
    def estimate_normals(points_xyz: np.ndarray, k: int = 100, r: float = 0.35) -> np.ndarray:
        """
        Compute surface normals using pptk PCA.
        """
        return np.abs(pptk.estimate_normals(points_xyz, k, r))

    @staticmethod
    def estimate_curvature(points_xyz: np.ndarray, k: int = 100, r: float = 0.35) -> np.ndarray:
        """
        Compute surface curvature using pptk eigenvalues.
        """
        eigens = np.abs(pptk.estimate_normals(points_xyz, k, r, output_eigenvalues=True)[0])
        eigens.sort(axis=1)
        return eigens[:, 0] / eigens.sum(axis=1) * 3.0

    @staticmethod
    def hough_lines(points_xy: np.ndarray, theta_precision: float = 0.5, angle_range: float = 90.0,
                    rho_precision: float = 0.02, theta_center: float = 0.0):
        """
        Hough transform for line detection on 2D points.
        """
        theta_precision_rad = np.radians(theta_precision)
        angle_range_rad = np.radians(angle_range)
        theta_center_rad = np.radians(theta_center)

        n_steps = int(angle_range_rad / theta_precision_rad)
        theta_idx = [i for i in range(-n_steps, n_steps + 1)]
        thetas = np.array([idx * theta_precision_rad + theta_center_rad for idx in theta_idx])
        cosines = np.array([np.cos(theta) for theta in thetas])
        tangents = np.array([np.tan(theta) for theta in thetas])

        votes = defaultdict(int)
        for point in tqdm(points_xy, desc='Finding lines'):
            rhos = np.array((point[1] - tangents * point[0]) * cosines / rho_precision, dtype=int)
            for rho, idx in zip(rhos, theta_idx):
                votes[(rho, idx)] += 1

        return votes, rho_precision, theta_precision_rad, theta_center_rad
