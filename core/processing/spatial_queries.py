"""
Spatial Queries and Bounding Box Operations.
"""
from typing import List, Tuple, Union
import numpy as np
import pandas as pd

class SpatialQueries:
    """
    Encapsulates 2D/3D box queries, proximity searches, and line geometric calculations.
    """
    @staticmethod
    def in_box_2d(box: Union[List, np.ndarray], points_xy: np.ndarray) -> np.ndarray:
        """
        Return a boolean mask indicating which points are within the given 2D bounding box (xy plane).
        box format: [min_point, max_point]
        """
        keep = points_xy > np.array(box[0])
        keep[points_xy > np.array(box[1])] = False
        return keep.all(axis=1)

    @staticmethod
    def make_box_from_point(point: Union[List, np.ndarray], delta: float) -> List[np.ndarray]:
        """
        Make a square bounding box with center at the given point and side lengths 2*delta.
        """
        point_arr = np.array(point)
        return [point_arr - delta, point_arr + delta]

    @staticmethod
    def distance_to_line(line: Tuple[Tuple[float, float], Tuple[float, float]], point: Tuple[float, float]) -> float:
        """
        Calculate the perpendicular Euclidean distance between a given point and a given 2D line.
        line format: ((x1, y1), (x2, y2))
        """
        p1, p2 = line
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        if not dx and not dy:
            return float(np.sqrt(np.square(point[0] - p1[0]) + np.square(point[1] - p1[1])))
        num = np.abs(dy * point[0] - dx * point[1] + p2[0] * p1[1] - p2[1] * p1[0])
        den = np.sqrt(np.square(dx) + np.square(dy))
        return float(num / den)

    @staticmethod
    def get_points_in_bounds(bounds: List[np.ndarray], points_xyz: np.ndarray, extra: float = 0.0) -> np.ndarray:
        """
        Return a boolean mask indicating which points are contained in the given bounds.
        """
        keep_min = (bounds[0][:2] - extra < points_xyz[:, :2]).all(axis=1)
        keep_max = (bounds[1][:2] + extra > points_xyz[:, :2]).all(axis=1)
        keep = keep_min & keep_max
        return keep
