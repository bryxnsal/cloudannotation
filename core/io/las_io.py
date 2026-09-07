"""
LAS / LAZ I/O Module: Reading and writing ASPRS LAS/LAZ point cloud files.
"""
import os
import subprocess
import numpy as np
import pandas as pd

class LasIO:
    """
    Handles reading and writing point clouds to/from LAS and LAZ formats.
    """
    @staticmethod
    def unzip_laz(infile, outfile=None):
        if outfile is None:
            outfile = infile.replace('.laz', '.las')
        args = ['laszip', '-i', infile, '-o', outfile]
        subprocess.run(" ".join(args), shell=True, stdout=subprocess.PIPE)
        return outfile

    @staticmethod
    def zip_las(infile, outfile=None):
        if outfile is None:
            outfile = infile.replace('.las', '.laz')
        args = ['laszip', '-i', infile, '-o', outfile]
        subprocess.run(" ".join(args), shell=True, stdout=subprocess.PIPE)
        return outfile

    @staticmethod
    def read(filename, max_points=None):
        import laspy
        is_laz = filename.endswith('.laz')
        read_file = filename
        if is_laz:
            read_file = LasIO.unzip_laz(filename, 'TEMPORARY.las')

        try:
            with laspy.file.File(read_file) as f:
                header = f.header.copy()
                total = f.header.point_records_count
                if max_points is not None and max_points < total:
                    choice = np.random.choice(total, max_points, replace=False)
                    mask = np.zeros(total, dtype=bool)
                    mask[choice] = True
                else:
                    mask = np.ones(total, dtype=bool)

                df = pd.DataFrame(np.array((f.x, f.y, f.z)).T[mask], columns=['x', 'y', 'z'])

                if f.header.data_format_id in [2, 3, 5, 7, 8]:
                    rgb = pd.DataFrame(
                        np.array((f.red, f.green, f.blue), dtype='int').T[mask],
                        columns=['r', 'g', 'b']
                    )
                    df = df.join(rgb)

                df['class'] = f.classification[mask].astype(int)
                if hasattr(f, 'user_data') and np.sum(f.user_data):
                    df['user_data'] = f.user_data[mask].copy()
                if hasattr(f, 'intensity') and np.sum(f.intensity):
                    df['intensity'] = f.intensity[mask].copy()

            return df, header
        finally:
            if is_laz and os.path.exists('TEMPORARY.las'):
                os.remove('TEMPORARY.las')

    @staticmethod
    def write(filename, points_df, header=None):
        import laspy
        is_laz = filename.endswith('.laz')
        target_las = 'TEMPORARY.las' if is_laz else filename

        if header is None:
            header = laspy.header.Header()
            header.x_offset, header.y_offset, header.z_offset = 0.0, 0.0, 0.0
            header.x_scale, header.y_scale, header.z_scale = 0.0001, 0.0001, 0.0001
        if header.data_format_id < 2:
            header.data_format_id = 2

        with laspy.file.File(target_las, header, mode='w') as f:
            f.x, f.y, f.z = points_df[['x', 'y', 'z']].values.T
            if 'r' in points_df.columns:
                f.red, f.green, f.blue = points_df[['r', 'g', 'b']].values.T
            if 'class' in points_df.columns:
                f.classification = points_df['class'].values.astype(int)
            if 'user_data' in points_df.columns:
                f.user_data = points_df['user_data'].values.astype(int)
            if 'intensity' in points_df.columns:
                f.intensity = points_df['intensity'].values.astype(int)

        if is_laz:
            LasIO.zip_las('TEMPORARY.las', filename)
            if os.path.exists('TEMPORARY.las'):
                os.remove('TEMPORARY.las')

        return filename
