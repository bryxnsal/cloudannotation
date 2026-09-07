"""
PointCloud: Lightweight Facade unifying 3D Point Cloud I/O, Viewer, History, Processing, and AI.
"""
import os
import datetime
import numpy as np
import pandas as pd

from Mask import Mask
import knn as knn
from core.viewer import CameraController, PptkViewerAdapter
from core.io import PointCloudIO, PlyIO
from core.history import UndoRedoManager
from core.processing import PointCloudTransforms, SpatialQueries, PointCloudFilters
from core.ai import AiManager
from core.data import SelectionManager, StatsManager


class PointCloud:
    """
    Facade class managing point cloud data, user interaction, rendering, and classification.
    Delegates heavy lifting to modular core engines.
    """
    def __init__(self, filename=None, point_size=0.01, max_points=10000000, render=True, labels=11, r=False, advanceFile=None):
        self.point_size = point_size
        self.max_points = max_points
        self.render_flag = render
        self.camera_controller = CameraController(lambda: self.viewer_adapter.viewer)
        self.viewer_adapter = PptkViewerAdapter(self.camera_controller)
        self.viewer_adapter.point_size = self.point_size
        self.resource = r
        self.las_header = None
        self.labels = labels
        self.points = pd.DataFrame(columns=['x', 'y', 'z', 'class'])
        self.colores = False
        self.showing = None
        self.index = None
        self.filename = filename
        self.saved_cameras = self.camera_controller.saved_cameras
        self.active_roi = None
        self.max_undo_steps = 50
        self.history_manager = UndoRedoManager(max_steps=self.max_undo_steps)
        self.undo_stack = self.history_manager.undo_stack
        self.redo_stack = self.history_manager.redo_stack
        self.base_classes = None
        self.full_cloud_lookat = None

        if filename is None:
            self.render_flag = False
        else:
            self.load(advanceFile if r else filename)
            if hasattr(self, 'points') and self.points is not None and 'class' in self.points.columns:
                self.base_classes = self.points['class'].to_numpy(copy=True)

    @property
    def viewer(self):
        """Backwards compatibility for self.viewer."""
        return self.viewer_adapter.viewer

    @viewer.setter
    def viewer(self, val):
        self.viewer_adapter.viewer = val

    def __del__(self):
        self.close_viewer()

    def __len__(self):
        return len(self.points)

    # ------------------ I/O Operations ------------------
    def load(self, filename, max_points=None):
        if max_points is not None:
            self.max_points = max_points
        try:
            new_df, metadata = PointCloudIO.load(filename, max_points=self.max_points, labels_count=self.labels)
        except ValueError as e:
            print(f'Cannot load {filename}: {e}')
            return

        if 'las_header' in metadata and metadata['las_header'] is not None:
            self.las_header = metadata['las_header']

        if hasattr(self, 'points') and self.points is not None and len(self.points) > 0:
            self.points = pd.concat([self.points, new_df], ignore_index=True, sort=False)
        else:
            self.points = new_df

        self.showing = Mask(len(self.points), True)
        self.render(self.showing)

    def __from_plyfile(self, filename):
        return PlyIO.read(filename, labels_count=self.labels)

    def save(self, filename=None):
        if filename is None or filename.strip() == '':
            filename = f"GlobalMap_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.ply"
        elif not filename.lower().endswith(".ply"):
            filename += ".ply"
        self.write(filename)
        print(f"Saved point cloud as: {filename}")

    def write(self, filename=None, mask=None, indices=None, highlighted=False, showing=False, overwrite=False, points=None):
        if filename is None:
            filename = self.filename
        target_path = filename
        if filename.endswith('.ply') and not os.path.dirname(filename) and self.filename:
            target_path = os.path.join(os.path.join(os.path.dirname(self.filename), 'advances'), filename)

        if os.path.exists(target_path) and not overwrite:
            print(target_path, 'already exists. Use option "overwrite=True" to overwrite')
            return

        if mask is None and points is None:
            mask = self.select(indices, highlighted, showing)
        if points is None:
            points = self.points.loc[mask.bools]

        try:
            PointCloudIO.save(target_path, points, las_header=self.las_header, labels_count=self.labels)
            print(f'Wrote {len(points)} points to {target_path}')
        except ValueError as e:
            print(f'Error writing file: {e}')

    def reload_from_file(self, filepath, preserve_camera=True, is_new_base=False):
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        cam_persp = self.get_perspective() if (preserve_camera and self.viewer_is_ready()) else None
        self.points = self.__from_plyfile(filepath)
        self.showing = Mask(len(self.points), True)
        self.clear_work_area()
        self.history_manager.clear()

        if is_new_base or self.base_classes is None:
            self.filename = filepath
            if 'class' in self.points.columns:
                self.base_classes = self.points['class'].to_numpy(copy=True)

        if self.viewer_is_ready():
            self.viewer_adapter.render(self.points, self.showing, preserve_camera=False)
            if cam_persp is not None and preserve_camera:
                self.set_perspective(cam_persp)
        else:
            self.render(self.showing, preserve_camera=preserve_camera)
        return True

    # ------------------ Viewer & Camera Management ------------------
    def prepare_viewer(self, render_flag=None):
        if render_flag is not None:
            self.render_flag = render_flag
        if not self.render_flag:
            return False
        if not self.viewer_is_ready():
            self.render(showing=True)
            return True

    def viewer_is_ready(self):
        return self.render_flag and self.viewer_adapter.is_ready()

    def close_viewer(self):
        self.viewer_adapter.close()

    def set_point_size(self, size):
        try:
            val = float(size)
            if val <= 0:
                return False
            self.point_size = val
            return self.viewer_adapter.set_point_size(val)
        except Exception as e:
            print("Error updating point size:", e)
            return False

    def update_attributes(self):
        if self.viewer_is_ready():
            self.viewer_adapter.update_attributes(self.points, self.showing)

    def render(self, mask=None, indices=None, highlighted=False, showing=False, invert=False, preserve_camera=True):
        if not self.render_flag:
            return
        if mask is None:
            mask = self.select(indices=indices, highlighted=highlighted, showing=showing, invert=invert)
        if not np.sum(mask[:]):
            return
        self.showing.set(mask[:])
        self.viewer_adapter.render(self.points, self.showing, preserve_camera=preserve_camera)

    def get_perspective(self):
        return self.camera_controller.get_perspective()

    def set_perspective(self, p):
        return self.camera_controller.set_perspective(p)

    def save_camera(self, name='default'):
        return self.camera_controller.save_camera(name)

    def restore_camera(self, name='default'):
        return self.camera_controller.restore_camera(name)

    # ------------------ Selection & ROI ------------------
    def get_relative_indices(self, mask, relative=None):
        return SelectionManager.get_relative_indices(mask, relative or self.showing)

    def get_highlighted_mask(self, invert=False):
        return SelectionManager.get_highlighted_mask(len(self.points), self.viewer_adapter, self.showing, invert=invert)

    def has_selection(self):
        if not self.viewer_is_ready():
            return False
        sel = self.viewer_adapter.get_selected_indices()
        return sel is not None and len(sel) > 0

    def highlight(self, mask=None, indices=None):
        if mask is None and indices is None:
            return
        if indices is not None:
            mask = self.select(indices=indices, highlighted=False)
        if self.viewer_is_ready():
            self.viewer_adapter.set_selected_indices(self.get_relative_indices(mask))

    def set_work_area(self, mask):
        self.active_roi = Mask(len(self.points), False)
        self.active_roi.bools = mask.bools.copy()

    def clear_work_area(self):
        self.active_roi = None

    def is_work_area_active(self):
        return self.active_roi is not None and np.sum(self.active_roi.bools) > 0

    def get_base_filename(self):
        return self.filename

    def get_advances_dir(self):
        return os.path.join(os.path.dirname(self.filename), 'advances') if self.filename else None

    def select(self, indices=None, highlighted=True, showing=False, classes=None, data=None, intensity=None,
               red=None, green=None, blue=None, compliment=False, invert=False):
        return SelectionManager.select(
            self.points,
            viewer_adapter=self.viewer_adapter,
            showing=self.showing,
            indices=indices,
            highlighted=highlighted,
            showing_flag=showing,
            classes=classes,
            data=data,
            intensity=intensity,
            red=red,
            green=green,
            blue=blue,
            compliment=compliment,
            invert=invert
        )

    # ------------------ Classification & History ------------------
    def classify(self, cls, overwrite=False, mask=None, preserve_camera=True):
        sel_indices = list(self.viewer_adapter.get_selected_indices()) if self.viewer_is_ready() else []
        if mask is None:
            mask = self.get_highlighted_mask()
        if not overwrite:
            mask.intersection(self.points['class'] == 0)

        modified_indices = np.where(mask.bools)[0]
        if len(modified_indices) > 0:
            old_classes = self.points.loc[modified_indices, 'class'].values.copy()
            self.history_manager.record_action(
                indices=modified_indices,
                old_classes=old_classes,
                new_class=cls,
                selection_indices=sel_indices
            )

        self.points.loc[mask.bools, 'class'] = cls
        if self.viewer_is_ready():
            self.update_attributes()
            self.viewer_adapter.set_selected_indices([])
            if not preserve_camera:
                self.render(showing=True, preserve_camera=False)
        elif self.render_flag and self.viewer is not None:
            self.render(showing=True, preserve_camera=preserve_camera)

    def undo(self):
        success, message, action = self.history_manager.undo(self.points)
        if not success:
            return False, message
        if self.viewer_is_ready():
            self.update_attributes()
            sel_indices = action.get('selection_indices', [])
            if sel_indices is not None and len(sel_indices) > 0:
                self.viewer_adapter.set_selected_indices(sel_indices)
            else:
                self.highlight(indices=action['indices'])
        return True, message

    def redo(self):
        success, message, action = self.history_manager.redo(self.points)
        if not success:
            return False, message
        if self.viewer_is_ready():
            self.update_attributes()
            self.viewer_adapter.set_selected_indices([])
        return True, message

    # ------------------ Transforms & Spatial Queries ------------------
    def center(self):
        PointCloudTransforms.center(self.points)

    def reset_origin(self):
        PointCloudTransforms.reset_origin(self.points)

    def subsample(self, n=10000000, percent=1.0):
        return PointCloudTransforms.subsample(len(self.points), n=n, percent=percent)

    def rotate(self, points=None, degrees=0.0, axes=['x', 'y']):
        if points is None:
            points = self.points.loc[self.showing.bools][axes].values
        return PointCloudTransforms.rotate(points, degrees=degrees)

    def slice(self, points=None, position=1.75, thickness=0.2, axis=2):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.slice(points, position=position, thickness=thickness, axis=axis)

    def in_box_2d(self, box, points=None):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y']].values
        return SpatialQueries.in_box_2d(box, points)

    @staticmethod
    def make_box_from_point(point, delta):
        return SpatialQueries.make_box_from_point(point, delta)

    def get_points_within(self, delta, point=None, return_mask=False, return_z=False, proportion=1.0):
        if proportion < 1.0:
            choice = np.random.choice(len(self), int(len(self) * proportion))
            pts = self.points.iloc[choice][['x', 'y']]
            if return_mask:
                print('From get_points_within: Doesn\'t make sense to return mask when proportion < 1.0')
                return []
        else:
            pts = self.points[['x', 'y']]
        if point is None:
            selected = self.get_highlighted_mask()
            point = np.average(self.points.loc[selected.bools][['x', 'y']], axis=0)
        x, y = point[:2]
        keep = (pts['x'] >= x - delta) & (pts['x'] <= x + delta) & (pts['y'] >= y - delta) & (pts['y'] <= y + delta)
        if return_mask:
            return keep.values
        return (self.points.loc[keep][['x', 'y', 'z']].values if return_z else pts.loc[keep][['x', 'y']].values)

    def distance_to_line(self, line, point):
        return SpatialQueries.distance_to_line(line, point)

    def get_points_near_line(self, line, delta=0.01):
        pts = self.points[['x', 'y']].values
        dists = np.array([SpatialQueries.distance_to_line(line, p) for p in pts])
        return np.where(dists < delta)[0]

    def get_points_in_bounds(self, bounds, points=None, extra=0.0):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return SpatialQueries.get_points_in_bounds(bounds, points, extra=extra)

    # ------------------ Filters & Alignments ------------------
    def rounding_filter(self, points=None, round=0.02):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.rounding_filter(points, round_val=round)

    def radial_filter(self, points=None, threshold=10, radius=0.05):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.radial_filter(points, threshold=threshold, radius=radius)

    def plane_filter(self, points=None, mesh=0.06, axis=2):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.plane_filter(points, mesh=mesh, axis=axis)

    def regularize(self, points=None, mesh=0.02):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.regularize(points, mesh=mesh)

    def normals(self, points=None, k=100, r=0.35, render=False):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        n = PointCloudFilters.estimate_normals(points, k=k, r=r)
        if render and self.viewer_is_ready():
            self.viewer.attributes(n)
        return n

    def curvature(self, points=None, k=100, r=0.35):
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.estimate_curvature(points, k=k, r=r)

    @staticmethod
    def hough_lines(points, theta_precision=0.5, angle_range=90, rho_precision=0.02, theta_center=0.0):
        return PointCloudFilters.hough_lines(
            points, theta_precision=theta_precision, angle_range=angle_range,
            rho_precision=rho_precision, theta_center=theta_center
        )

    def auto_align_bound_box_method(self, tolerance=0.1, max_points=10000, thickness=0.2):
        best_angle = PointCloudFilters.auto_align_bound_box(
            self.points[['x', 'y']].values, tolerance=tolerance, max_points=max_points, thickness=thickness
        )
        if best_angle:
            self.points[['x', 'y']] = self.rotate(degrees=best_angle)
            self.render(showing=True)
        return best_angle

    def auto_align_hough_line_method(self, tolerance=0.1, max_points=100000):
        angle = PointCloudFilters.auto_align_hough_line(
            self.points[['x', 'y']].values, tolerance=tolerance, max_points=max_points
        )
        self.points[['x', 'y']] = self.rotate(degrees=angle)
        self.render(showing=True)

    def neighbors(self, k=100, highlight=True):
        mask = self.select(showing=False, highlighted=True)
        if not mask.count() or mask.count() == len(self.points):
            print('No points were selected')
            return
        pts = self.points.loc[mask.bools][['x', 'y', 'z']]
        query = pts if len(pts) == 1 else np.average(pts, axis=0)
        if self.index is None:
            self.index = knn.Query()
            self.index.pptk(self.points.loc[self.showing.bools][['x', 'y', 'z']].values)
        mask.setr(self.index.neighbors(query, k))
        if highlight:
            self.highlight(mask)
        return mask

    def color_groups(self, groups, store=False, render=True):
        labels = np.zeros(len(self.points), dtype=int)
        if not len(groups):
            return []
        elif not isinstance(groups[0], list):
            groups = [groups]
        for indices in groups:
            if len(indices):
                labels[indices] = np.random.randint(1, 32)
        if render and self.viewer_is_ready():
            self.viewer.attributes(labels[self.showing.bools])
        if store:
            self.points['user_data'] = labels
        else:
            return labels

    # ------------------ Statistics & Utilities ------------------
    def get_stats(self):
        return StatsManager.get_stats(
            self.points,
            filename=self.filename,
            point_size=self.point_size,
            base_classes=self.base_classes
        )

    # ------------------ AI Assisted Tools ------------------
    def ai_auto_ground(self, cell_size=1.0, distance_threshold=0.25, overwrite=False):
        return AiManager.auto_ground(self, cell_size=cell_size, distance_threshold=distance_threshold, overwrite=overwrite)

    def ai_classify_pole(self, height_threshold=12.0, cylinder_radius=0.55, overwrite=False):
        return AiManager.classify_pole(self, height_threshold=height_threshold, cylinder_radius=cylinder_radius, overwrite=overwrite)

    def ai_grow_cable(self, min_clearance=1.5, overwrite=False):
        return AiManager.grow_cable(self, min_clearance=min_clearance, overwrite=overwrite)

    def ai_classify_veg(self, min_clearance=0.35, overwrite=False):
        return AiManager.classify_veg(self, min_clearance=min_clearance, overwrite=overwrite)
