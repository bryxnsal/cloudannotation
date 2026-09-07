"""
PLY I/O Module: Reading and writing PLY point cloud files using PlyData.
"""
import os
import numpy as np
import pandas as pd
from plyfile import PlyData, PlyElement

class PlyIO:
    """
    Handles reading and writing point clouds to/from Polygon File Format (.ply).
    """
    @staticmethod
    def read(filename, labels_count=None):
        """
        Read PLY file into a standardized pandas DataFrame.
        """
        plydata = PlyData.read(filename)
        vertex = plydata['vertex'].data

        data = {name: vertex[name] for name in vertex.dtype.names}
        df = pd.DataFrame(data)

        # Validate required columns
        for col in ['x', 'y', 'z']:
            if col not in df.columns:
                raise ValueError(f"Missing required column '{col}' in PLY file: {filename}")

        # Normalize RGB colors
        if 'red' in df.columns and 'green' in df.columns and 'blue' in df.columns:
            df.rename(columns={'red': 'r', 'green': 'g', 'blue': 'b'}, inplace=True)

        # Process class labels
        if 'class' in df.columns:
            df['class'] = df['class'].astype(int)
        elif 'scalar_Label' in df.columns:
            df['class'] = df['scalar_Label'].astype(int)
        elif 'r' in df.columns and labels_count is not None:
            if df['r'].max() <= 1.0:
                df['class'] = np.round(df['r'] * float(labels_count)).astype(int)
            else:
                df['class'] = df['r'].astype(int)
        else:
            df['class'] = 0

        # Map secondary scalar fields
        if 'g' in df.columns and 'user_data' not in df.columns:
            df['user_data'] = df['g']
        if 'b' in df.columns and 'intensity' not in df.columns:
            df['intensity'] = df['b']

        return df

    @staticmethod
    def write(output_path, points_df, include_rgb=None):
        """
        Write points DataFrame out to binary PLY format.
        """
        for col in ['x', 'y', 'z']:
            if col not in points_df.columns:
                raise ValueError(f"Missing required column '{col}' in points DataFrame")

        folder = os.path.dirname(output_path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

        xyz = points_df[['x', 'y', 'z']].to_numpy(dtype=np.float32)

        if 'class' in points_df.columns:
            cls = points_df['class'].fillna(-1).astype(np.int32).to_numpy()
        else:
            cls = -1 * np.ones(len(points_df), dtype=np.int32)

        if include_rgb is None:
            include_rgb = all(col in points_df.columns for col in ['r', 'g', 'b'])

        if include_rgb:
            rgb = points_df[['r', 'g', 'b']].to_numpy(dtype=np.uint8)
            vertex_dtype = [
                ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
                ('red', 'u1'), ('green', 'u1'), ('blue', 'u1'),
                ('class', 'i4')
            ]
        else:
            vertex_dtype = [
                ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
                ('class', 'i4')
            ]

        vertex_array = np.empty(len(points_df), dtype=vertex_dtype)
        vertex_array['x'] = xyz[:, 0]
        vertex_array['y'] = xyz[:, 1]
        vertex_array['z'] = xyz[:, 2]
        vertex_array['class'] = cls

        if include_rgb:
            vertex_array['red'] = rgb[:, 0]
            vertex_array['green'] = rgb[:, 1]
            vertex_array['blue'] = rgb[:, 2]

        el = PlyElement.describe(vertex_array, 'vertex')
        PlyData([el], text=False).write(output_path)
        return output_path
