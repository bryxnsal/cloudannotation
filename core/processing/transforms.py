"""
Geometric transformations module for point clouds: centering, origin reset, subsampling, and rotation.
"""
import numpy as np
import pandas as pd

class PointCloudTransforms:
    """
    Handles coordinate transformations and geometric manipulations.
    """
    @staticmethod
    def center(points_df: pd.DataFrame) -> None:
        """
        Shift the origin of the point cloud to its centroid in-place.
        """
        points_df[['x', 'y', 'z']] -= np.average(points_df[['x', 'y', 'z']], axis=0)

    @staticmethod
    def reset_origin(points_df: pd.DataFrame) -> None:
        """
        Shift the origin of the point cloud to its minimum bound in-place.
        """
        points_df[['x', 'y', 'z']] -= points_df[['x', 'y', 'z']].values.min(axis=0)

    @staticmethod
    def subsample(total_points: int, n: int = 10000000, percent: float = 1.0) -> np.ndarray:
        """
        Return a boolean mask representing a random sample of points.
        """
        threshold = int(percent * total_points)
        if n < threshold:
            threshold = n
        if threshold < total_points:
            keep = np.zeros(total_points, dtype=bool)
            keep[np.random.choice(total_points, threshold, replace=False)] = True
            return keep
        else:
            return np.ones(total_points, dtype=bool)

    @staticmethod
    def rotate(points: np.ndarray, degrees: float = 0.0) -> np.ndarray:
        """
        Rotate 2D points (x, y) by 'degrees' degrees around the origin.
        """
        t = np.radians(degrees)
        rot = np.array(((np.cos(t), -np.sin(t)), (np.sin(t), np.cos(t))))
        return np.dot(points, rot)
