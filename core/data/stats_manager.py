"""
StatsManager: Computes point cloud dataset summaries, label distributions, and change tracking.
"""
import os
import datetime
from typing import Dict, Any, Optional
import pandas as pd
from plyfile import PlyData


class StatsManager:
    """
    Computes point counts, class frequencies, delta from original baseline, and file metadata.
    """

    @staticmethod
    def get_stats(points_df: pd.DataFrame,
                  filename: Optional[str] = None,
                  point_size: float = 0.01,
                  base_classes: Optional[Any] = None) -> Dict[str, Any]:
        total_pts = len(points_df) if points_df is not None else 0
        labeled_pts, changed_pts = 0, 0
        classes_count = {}

        if total_pts > 0 and 'class' in points_df.columns:
            classes_count = points_df['class'].value_counts().to_dict()
            labeled_pts = int((points_df['class'] > 0).sum())

            if base_classes is None and filename and os.path.isfile(filename):
                try:
                    p = PlyData.read(filename)
                    if 'class' in p['vertex'].data.dtype.names:
                        base_classes = p['vertex'].data['class'].copy()
                except Exception:
                    pass

            if base_classes is not None and len(base_classes) == total_pts:
                changed_pts = int((points_df['class'].to_numpy() != base_classes).sum())

        file_size_mb, file_mtime = 0.0, None
        if filename and os.path.isfile(filename):
            file_size_mb = os.path.getsize(filename) / (1024 * 1024)
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filename))

        return {
            'filename': os.path.basename(filename) if filename else 'Unknown',
            'filepath': filename,
            'total_points': total_pts,
            'point_size': point_size,
            'labeled_points': labeled_pts,
            'labeled_ratio': (labeled_pts / total_pts * 100.0) if total_pts > 0 else 0.0,
            'changed_points': changed_pts,
            'changed_ratio': (changed_pts / total_pts * 100.0) if total_pts > 0 else 0.0,
            'file_size_mb': file_size_mb,
            'mtime': file_mtime,
            'classes_count': classes_count
        }
