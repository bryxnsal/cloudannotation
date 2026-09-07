"""
XYZ & PCD I/O Module: Handling ASCII formats (xyz, pts, txt, csv) and Open3D PCD files.
"""
import os
import numpy as np
import pandas as pd
import open3d as o3d

class XyzIO:
    """
    Handles reading and writing text-based coordinates (.xyz, .pts, .txt, .csv) and .pcd.
    """
    @staticmethod
    def read_xyz(filename):
        with open(filename) as f:
            first_line = f.readline()
            split_first_line = first_line.split(',')
            if split_first_line[0] == first_line:
                split_first_line = first_line.split(' ')
                delimiter = ' '
            else:
                delimiter = ','

            has_header = first_line.lower().islower()
            if has_header:
                header = 0
                names = split_first_line
            else:
                header = None
                names = ['x', 'y', 'z', 'class', 'r', 'g', 'b'][:len(split_first_line)]

            if has_header and not len(split_first_line[0]):
                names = names[1:]

        df = pd.read_csv(filename, sep=delimiter, header=header, names=names)
        return df

    @staticmethod
    def write_xyz(filename, points_df):
        points_df.to_csv(filename, index=False)
        return filename

    @staticmethod
    def read_pcd(filename):
        cloud = o3d.io.read_point_cloud(filename)
        df = pd.DataFrame(np.asarray(cloud.points), columns=['x', 'y', 'z'])
        if cloud.has_colors():
            colors = (np.asarray(cloud.colors) * 255.0).astype(int)
            df['r'] = colors[:, 0]
            df['g'] = colors[:, 1]
            df['b'] = colors[:, 2]
        df['class'] = 0
        return df

    @staticmethod
    def write_pcd(filename, points_df, labels_count=None):
        cloud = o3d.geometry.PointCloud()
        cloud.points = o3d.utility.Vector3dVector(points_df[['x', 'y', 'z']].values)
        if all(col in points_df.columns for col in ['r', 'g', 'b']):
            colors = points_df[['r', 'g', 'b']].values / 255.0
            cloud.colors = o3d.utility.Vector3dVector(colors)
        elif 'class' in points_df.columns and labels_count:
            colors = np.zeros((len(points_df), 3))
            colors[:, 0] = points_df['class'] / float(labels_count)
            if 'user_data' in points_df.columns:
                colors[:, 1] = points_df['user_data'] / 255.0
            if 'intensity' in points_df.columns:
                colors[:, 2] = points_df['intensity'] / 255.0
            if colors.max() > 0:
                cloud.colors = o3d.utility.Vector3dVector(colors)
        o3d.io.write_point_cloud(filename, cloud)
        return filename

