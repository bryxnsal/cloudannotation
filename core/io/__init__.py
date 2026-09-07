"""
IO Package: Universal reader and writer for multiple point cloud formats.
"""
import os
from core.io.ply_io import PlyIO
from core.io.las_io import LasIO
from core.io.xyz_io import XyzIO

class PointCloudIO:
    """
    Unified entry point for loading and saving point clouds across formats.
    """
    @staticmethod
    def load(filename, max_points=None, labels_count=None):
        """
        Load point cloud from supported file extension.
        Returns: (pandas.DataFrame, extra_metadata_dict)
        """
        lower = filename.lower()
        metadata = {}

        if lower.endswith('.ply'):
            df = PlyIO.read(filename, labels_count=labels_count)
        elif lower.endswith('.las') or lower.endswith('.laz'):
            df, header = LasIO.read(filename, max_points=max_points)
            metadata['las_header'] = header
        elif lower.endswith('.pcd'):
            df = XyzIO.read_pcd(filename)
        elif any(lower.endswith(ext) for ext in ['.xyz', '.pts', '.txt', '.csv']):
            df = XyzIO.read_xyz(filename)
        else:
            raise ValueError(f"Unsupported file format for: {filename}")

        if max_points is not None and len(df) > max_points:
            df = df.sample(n=max_points, random_state=42).reset_index(drop=True)

        return df, metadata

    @staticmethod
    def save(filename, points_df, las_header=None, include_rgb=None, labels_count=None):
        """
        Save point cloud DataFrame to specified file format.
        """
        lower = filename.lower()
        if lower.endswith('.ply'):
            return PlyIO.write(filename, points_df, include_rgb=include_rgb)
        elif lower.endswith('.las') or lower.endswith('.laz'):
            return LasIO.write(filename, points_df, header=las_header)
        elif lower.endswith('.pcd'):
            return XyzIO.write_pcd(filename, points_df, labels_count=labels_count)
        elif any(lower.endswith(ext) for ext in ['.xyz', '.pts', '.txt', '.csv']):
            return XyzIO.write_xyz(filename, points_df)
        else:
            raise ValueError(f"Unsupported export file format for: {filename}")


__all__ = ['PointCloudIO', 'PlyIO', 'LasIO', 'XyzIO']
