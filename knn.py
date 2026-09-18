
try:
    from pptk import kdtree
    HAS_PPTK = True
except (ImportError, OSError):
    kdtree = None
    HAS_PPTK = False

from scipy.spatial import KDTree
import numpy as np


class Query:
    def __init__(self):
        self.pptk_index = None
        self.pptk_n = 0
        self.scipy_index = None
        self.scipy_n = 0

    def __len__(self):
        if self.pptk_n:
            return self.pptk_n
        elif self.scipy_n:
            return self.scipy_n
        else:
            return 0

    def delete_pptk(self):
        self.pptk_index = None
        self.pptk_n = 0

    def delete_scipy(self):
        self.scipy_index = None
        self.scipy_n = 0

    def neighbors(self, query, k=100, radius=np.power(10, 10), distances=False, manhatten=False, approx=0.0):
        if self.pptk_index is not None:
            try:
                neighbors = kdtree._query(self.pptk_index, query, k, radius)[0]
            except ValueError:
                neighbors = kdtree._query(self.pptk_index, np.array([query]), k, radius)[0]
            if distances:
                dists = np.zeros(len(neighbors))
        elif self.scipy_index is not None:
            if manhatten:
                p = 1.0
            else:
                p = 2.0
            dists, neighbors = self.scipy_index.query(query, k, eps=approx, p=p, distance_upper_bound=radius)
            mask = radius >= dists
            neighbors, dists = neighbors[mask], dists[mask]
        elif self.voxel_index is not None:
            neighbors = self.voxel_index.neighbors(query, k)
            dists = self.voxel_index.distances(query, neighbors)
        else:
            neighbors, dists = [], []
            print('No query index built')

        if distances:
            return neighbors, dists
        else:
            return neighbors

    def pptk(self, points):
        if self.pptk_index is not None:
            self.delete_pptk()
        if kdtree is not None:
            self.pptk_index = kdtree._build(points)
            self.pptk_n = len(points)
        else:
            # Fallback to SciPy KDTree seamlessly on platforms without PPTK (e.g. Windows)
            self.scipy(points)

    def scipy(self, points, leaf_size=100):
        if self.scipy_index is not None:
            self.delete_scipy()
        try:
            self.scipy_index = KDTree(points, leafsize=leaf_size)
            self.scipy_n = len(points)
        except RecursionError:
            if leaf_size < 1000000:
                self.scipy(points, leaf_size * 10)
            else:
                print('Building scipy index failed')
