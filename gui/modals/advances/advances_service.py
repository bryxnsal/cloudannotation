"""
AdvancesService: Pure domain logic for scanning, analyzing, backing up and restoring advances.
Completely decoupled from Tkinter views.
"""
import os
import shutil
import datetime
from plyfile import PlyData
import numpy as np

class AdvancesService:
    """
    Handles point cloud advances I/O, diff calculations vs base, and backup operations.
    """
    def __init__(self, pc):
        self.pc = pc

    def get_base_classes(self):
        """
        Retrieve base point cloud classes array.
        Uses in-memory cache if present, otherwise reads from base file.
        """
        if hasattr(self.pc, 'base_classes') and self.pc.base_classes is not None:
            return self.pc.base_classes

        base_path = self.pc.filename
        if base_path and os.path.isfile(base_path):
            try:
                p = PlyData.read(base_path)
                if 'class' in p['vertex'].data.dtype.names:
                    return p['vertex'].data['class']
            except Exception as e:
                print("AdvancesService: Error reading base file {}: {}".format(base_path, e))
        return None

    def get_file_info(self, filepath, base_classes=None):
        """
        Analyze an advance PLY file: size, mtime, points count, and vector comparison vs base.
        """
        try:
            stat = os.stat(filepath)
            mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_mb = "{:.1f} MB".format(stat.st_size / (1024 * 1024))

            plydata = PlyData.read(filepath)
            v_data = plydata['vertex'].data
            total_pts = len(v_data)

            changed_pts = 0
            changed_ratio_str = "0.0%"
            if 'class' in v_data.dtype.names and base_classes is not None and len(base_classes) == total_pts:
                cls_arr = v_data['class']
                changed_pts = int((cls_arr != base_classes).sum())
                if total_pts > 0:
                    changed_ratio_str = "{:.2f}%".format(changed_pts / float(total_pts) * 100.0)

            return {
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'mtime': mtime,
                'size_mb': size_mb,
                'total_pts': total_pts,
                'changed_pts': changed_pts,
                'changed_ratio_str': changed_ratio_str,
                'raw_mtime': stat.st_mtime
            }
        except Exception as e:
            print("AdvancesService: Error reading file {}: {}".format(filepath, e))
            return None

    def list_advances(self):
        """
        Scan advances directory and return list of advances sorted newest first.
        """
        base_classes = self.get_base_classes()
        advances_dir = self.pc.get_advances_dir()
        if not advances_dir or not os.path.isdir(advances_dir):
            return [], "No advances folder found."

        ply_files = [
            os.path.join(advances_dir, f)
            for f in os.listdir(advances_dir)
            if f.lower().endswith('.ply')
        ]

        if not ply_files:
            return [], "No advances saved yet in advances directory."

        advances_list = []
        for pf in ply_files:
            info = self.get_file_info(pf, base_classes)
            if info:
                advances_list.append(info)

        advances_list.sort(key=lambda x: x['raw_mtime'], reverse=True)
        summary = "Found {} advance(s).".format(len(advances_list))
        return advances_list, summary

    def load_advance_into_viewer(self, advance_info):
        """
        Reload working point cloud with selected advance.
        """
        filepath = advance_info['filepath']
        self.pc.reload_from_file(filepath, preserve_camera=True, is_new_base=False)
        return True

    def overwrite_base_ply(self, advance_info):
        """
        Backup current base file to .bak and replace base file with selected advance.
        """
        base_path = self.pc.filename
        if not base_path or not os.path.isfile(base_path):
            raise FileNotFoundError("Base PLY file could not be located.")

        advance_path = advance_info['filepath']
        bak_path = base_path + ".bak"

        # 1. Create safety backup
        shutil.copy2(base_path, bak_path)

        # 2. Overwrite base file with selected advance
        shutil.copy2(advance_path, base_path)

        # 3. Reload in PointCloud as new base
        self.pc.reload_from_file(base_path, preserve_camera=True, is_new_base=True)
        return base_path, bak_path

    def restore_base_ply(self):
        """
        Restore base PLY file from .bak if present, or reload original base file.
        """
        base_path = self.pc.filename
        if not base_path:
            raise FileNotFoundError("Base PLY filename is not specified.")

        bak_path = base_path + ".bak"
        has_bak = os.path.isfile(bak_path)

        if has_bak:
            shutil.copy2(bak_path, base_path)

        self.pc.reload_from_file(base_path, preserve_camera=True, is_new_base=True)
        return base_path, has_bak
