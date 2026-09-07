import collections
import datetime
#from laspy.file import File
#from laspy.header import Header
import laspy
import open3d as o3d
import numpy as np
import pandas as pd
import pptk
import os
from pptk.points.points import points
from tqdm import tqdm
from collections import defaultdict
import math
from Mask import Mask
import knn as knn
from Voxelize import VoxelGrid
from plyfile import PlyData, PlyElement
from core.viewer import CameraController, PptkViewerAdapter
from core.io import PointCloudIO, PlyIO
from core.history import UndoRedoManager
from core.processing import PointCloudTransforms, SpatialQueries, PointCloudFilters
from core.ai import GroundDetector, PoleDetector, CableDetector, VegetationDetector





class PointCloud:
    def __init__(self, filename=None, point_size=0.01, max_points=10000000, render=True, labels=11,r=False,advanceFile=None):

        self.point_size = point_size
        self.max_points = max_points
        self.render_flag = render
        self.viewer = None
        self.camera_controller = CameraController(lambda: self.viewer)
        self.viewer_adapter = PptkViewerAdapter(self.camera_controller)
        self.resource = r
        self.las_header = None
        self.labels = labels
        self.points = pd.DataFrame(columns=['x', 'y', 'z', 'class'])
        self.colores =False
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
            if r:
                self.load(advanceFile)
            else:
                self.load(filename)
            if hasattr(self, 'points') and self.points is not None and 'class' in self.points.columns:
                self.base_classes = self.points['class'].to_numpy(copy=True)

    def __del__(self):
        if self.viewer:
            self.viewer.close()

    def __len__(self):
        return len(self.points)

    def load(self, filename, max_points=None):
        if max_points is not None:
            self.max_points = max_points
        try:
            new_df, metadata = PointCloudIO.load(
                filename,
                max_points=self.max_points,
                labels_count=self.labels
            )
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
        """Internal helper maintained for compatibility, delegating to PlyIO."""
        return PlyIO.read(filename, labels_count=self.labels)


    def writeLabels(self):
        writeLabeled(self.filename, self.points)

    def renderLabel(self, array):
        count = np.sum(np.isin(self.points['class'], array))
        if count > 0:
            self.render(self.select(classes=array))
        else:
            print('No points to render')

    def renderLabels(self, init, last):
        self.render(self.select(classes=range(init, last)))

    def clearLabel(self, label):
        self.points.loc[self.points['class'] == label, ['class']] = 0

    def export(self):
       writeLabeled(self.filename, self.points)

    def save(self, filename=None):
        # If no filename is provided, generate one using datetime
        if filename is None or filename.strip() == '':
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"GlobalMap_{timestamp}.ply"
        elif not filename.lower().endswith(".ply"):
            filename += ".ply"

        self.write(filename)
        print(f"Saved point cloud as: {filename}")

    def write(self, filename=None, mask=None, indices=None, highlighted=False, showing=False, overwrite=False, points=None):
        """
        This function allows the user to write out a subset of the current points to a file.
        :param filename: Output filename to write to. Default is {current_filename}_out.las.
        :param mask: Mask object used to indicate which points to write to file.
        :param indices: List of integer indices indicating which points to write to file.
        :param highlighted: If True, then write the currently highlighted points to file.
        :param showing: If True, then write all the currently rendered points to file.
        :param overwrite: If True, then overwrite an existing file
        :param points: Pandas DataFrame containing the points and all the data to write.
        """
        if filename is None:
            filename = self.filename
        
        # If relative PLY path and filename doesn't specify a dir, store in advances/
        target_path = filename
        if filename.endswith('.ply') and not os.path.dirname(filename) and self.filename:
            folder = os.path.join(os.path.dirname(self.filename), 'advances')
            target_path = os.path.join(folder, filename)

        if os.path.exists(target_path) and not overwrite:
            print(target_path, 'already exists. Use option "overwrite=True" to overwrite')
            return

        if mask is None and points is None:
            mask = self.select(indices, highlighted, showing)
        if points is None:
            points = self.points.loc[mask.bools]

        try:
            PointCloudIO.save(
                target_path,
                points,
                las_header=self.las_header,
                labels_count=self.labels
            )
            print(f'Wrote {len(points)} points to {target_path}')
        except ValueError as e:
            print(f'Error writing file: {e}')


    def prepare_viewer(self, render_flag=None):
        """
        Check to see if the viewer is ready to receive commands. If it isn't, get it ready and return True.
        If the render flag is False, return False.
        """
        if render_flag is not None:
            self.render_flag = render_flag
        if not self.render_flag:
            return False
        if not self.viewer_is_ready():
            self.render(showing=True)
            return True

    def viewer_is_ready(self):
        """
        Return True if the viewer is ready to receive commands, else return False.
        """
        if not self.render_flag or not self.viewer:
            return False
        try:
            self.viewer.get('lookat')
            return True
        except ConnectionRefusedError:
            return False

    def close_viewer(self):
        if self.viewer_is_ready():
            self.viewer.close()
        self.viewer = None

    def set_point_size(self, size):
        """
        Dynamically update point display size in memory and in active pptk viewer.
        """
        try:
            val = float(size)
            if val <= 0:
                return False
            self.point_size = val
            if self.viewer_is_ready():
                self.viewer.set(point_size=self.point_size)
            return True
        except Exception as e:
            print("Error updating point size:", e)
            return False

    def update_attributes(self):
        """
        Refresh attributes (colors, classes, user_data, intensity) of currently rendered points
        without clearing the geometry buffer or resetting the camera.
        """
        if not self.viewer_is_ready():
            return
        mask = self.showing
        if 'r' in self.points:
            scale = 255.0
            if 'user_data' in self.points and 'intensity' in self.points:
                self.viewer.attributes(self.points.loc[mask[:], ['r', 'g', 'b']] / scale,
                                       self.points.loc[mask[:], 'class'],
                                       self.points.loc[mask[:], 'user_data'],
                                       self.points.loc[mask[:], 'intensity'])
            elif 'user_data' in self.points:
                self.viewer.attributes(self.points.loc[mask[:], ['r', 'g', 'b']] / scale,
                                       self.points.loc[mask[:], 'class'],
                                       self.points.loc[mask[:], 'user_data'])
            elif 'intensity' in self.points:
                self.viewer.attributes(self.points.loc[mask[:], ['r', 'g', 'b']] / scale,
                                       self.points.loc[mask[:], 'class'],
                                       self.points.loc[mask[:], 'intensity'])
            else:
                self.viewer.attributes(self.points.loc[mask[:], ['r', 'g', 'b']] / scale,
                                       self.points.loc[mask[:], 'class'])
        else:
            self.viewer.attributes(self.points.loc[mask[:], 'class'])

    def render(self, mask=None, indices=None, highlighted=False, showing=False, invert=False, preserve_camera=True):
        """
        This function allows the user to render some selection of the points to the viewer.
        By default, this function will render all points when called. If a mask is supplied, then those points
        will be rendered. If the highlighted or showing flags are True, then the appropriate selection will be used.
        :param mask: Mask object indicating which points to render.
        :param highlighted: If True, then render the currently highlighted points.
        :param showing: If True, then re-render all of the currently rendered points.
        :param preserve_camera: If True, preserves current camera orientation and position.
        """
        print("\nRendering\n")
        if not self.render_flag:
            return

        cam_persp = None
        if preserve_camera and self.viewer_is_ready():
            cam_persp = self.get_perspective()

        if mask is None:
            mask = self.select(
                indices=indices, highlighted=highlighted, showing=showing, invert=invert)

        if not np.sum(mask[:]):
            return

        self.showing.set(mask[:])

        if self.viewer_is_ready():
            self.viewer.clear()
            self.viewer.load(self.points.loc[mask[:], ['x', 'y', 'z']])
        else:
            pcd = self.points.loc[mask[:]][['x', 'y', 'z']]
            self.viewer = pptk.viewer(pcd)

        self.viewer.set(point_size=self.point_size, selected=[])
        self.update_attributes()

        if cam_persp is not None and preserve_camera:
            self.set_perspective(cam_persp)


    def renderClass(self,colores=True, mask=None, indices=None, highlighted=False, showing=False, invert=False):
        """
        This function allows the user to render some selection of the points to the viewer.
        By default, this function will render all points when called. If a mask is supplied,
        then those points
        will be rendered. If the highlighted or showing flags are True,
        then the appropriate selection will be used.
        :param mask: Mask object indicating which points to render.
        :param highlighted: If True, then render the currently highlighted points.
        :param showing: If True, then re-render all of the currently rendered points.
        """
        print("Rendering")
        if not self.render_flag:
            return

        if mask is None:
            mask = self.select(
                indices=indices, highlighted=highlighted, showing=showing, invert=invert)

        if not np.sum(mask[:]):
            return

        self.showing.set(mask[:])
        '''
        if self.viewer_is_ready():
            self.viewer.clear()
            self.viewer.load(self.points.loc[mask[:], ['x', 'y', 'z']])
        else:
            pcd = self.points.loc[mask[:]][['x', 'y', 'z']]
            self.viewer = pptk.viewer(pcd)

        self.viewer.set(point_size=self.point_size, selected=[])
        '''   
        if colores is True:
            if 'r' in self.points:
                scale = 255.0
                self.viewer.attributes(self.points.loc[mask[:], ['r', 'g', 'b']] / scale,
                                           self.points.loc[mask[:], 'class'])
        else:
            self.viewer.attributes(self.points.loc[mask[:], 'class'])
            print("esta en 5")



    def get_relative_indices(self, mask, relative=None):
        """
        Return the chosen point indices relative to the currently rendered points (or some other set).
        """
        if relative is None:
            relative = self.showing
        mask.bools = mask.bools[relative.bools]
        return mask.resolve()

    def get_highlighted_mask(self, invert=False):
        """
        Return a mask indicating which points are currently highlighted in the viewer.
        """
        mask = Mask(len(self.points), False)
        if self.viewer_is_ready():
            try:
                selection = self.viewer.get('selected')
            except Exception:
                selection = []
            if selection is None or len(selection) == 0:
                if invert:
                    mask.bools = self.showing.bools.copy()
                return mask
            if invert:
                unselection = np.arange(0, len(self.points))
                unselection = unselection[np.in1d(
                    unselection, selection, invert=True)]
                mask.setr_subset(unselection, self.showing)
                return mask
            else:
                mask.setr_subset(selection, self.showing)
                return mask
        return mask

    def has_selection(self):
        """Return True if points are currently highlighted in viewer."""
        if not self.viewer_is_ready():
            return False
        try:
            sel = self.viewer.get('selected')
            return sel is not None and len(sel) > 0
        except Exception:
            return False

    def set_work_area(self, mask):
        """Lock active work area ROI."""
        self.active_roi = Mask(len(self.points), False)
        self.active_roi.bools = mask.bools.copy()

    def clear_work_area(self):
        """Clear active work area ROI."""
        self.active_roi = None

    def is_work_area_active(self):
        """Check if work area ROI is currently active."""
        return self.active_roi is not None and np.sum(self.active_roi.bools) > 0

    def get_base_filename(self):
        """Return base PLY filename."""
        return self.filename

    def get_advances_dir(self):
        """Return directory where advances for this cloud are stored."""
        if not self.filename:
            return None
        return os.path.join(os.path.dirname(self.filename), 'advances')

    def get_stats(self):
        """Return summary dictionary of point cloud metadata and labels."""
        total_pts = len(self.points) if hasattr(self, 'points') and self.points is not None else 0
        labeled_pts = 0
        changed_pts = 0
        classes_count = {}
        if total_pts > 0 and 'class' in self.points.columns:
            counts = self.points['class'].value_counts()
            classes_count = counts.to_dict()
            labeled_pts = int((self.points['class'] > 0).sum())

            # If base_classes is not set yet, initialize from base file or current points
            if self.base_classes is None and self.filename and os.path.isfile(self.filename):
                try:
                    p = PlyData.read(self.filename)
                    if 'class' in p['vertex'].data.dtype.names:
                        self.base_classes = p['vertex'].data['class'].copy()
                except Exception:
                    pass

            if self.base_classes is not None and len(self.base_classes) == total_pts:
                cur_cls = self.points['class'].to_numpy()
                changed_pts = int((cur_cls != self.base_classes).sum())

        file_size_mb = 0.0
        file_mtime = None
        if self.filename and os.path.isfile(self.filename):
            file_size_mb = os.path.getsize(self.filename) / (1024 * 1024)
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(self.filename))

        return {
            'filename': os.path.basename(self.filename) if self.filename else 'Unknown',
            'filepath': self.filename,
            'total_points': total_pts,
            'point_size': self.point_size,
            'labeled_points': labeled_pts,
            'labeled_ratio': (labeled_pts / total_pts * 100.0) if total_pts > 0 else 0.0,
            'changed_points': changed_pts,
            'changed_ratio': (changed_pts / total_pts * 100.0) if total_pts > 0 else 0.0,
            'file_size_mb': file_size_mb,
            'mtime': file_mtime,
            'classes_count': classes_count
        }

    def reload_from_file(self, filepath, preserve_camera=True, is_new_base=False):
        """Reload points from a given file (e.g. an advance or base file) into working memory."""
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        cam_persp = None
        if preserve_camera and self.viewer_is_ready():
            cam_persp = self.get_perspective()

        # Load new dataframe
        df = self.__from_plyfile(filepath)
        self.points = df
        self.showing = Mask(len(self.points), True)
        self.clear_work_area()
        self.history_manager.clear()


        if is_new_base or self.base_classes is None:
            self.filename = filepath
            if 'class' in self.points.columns:
                self.base_classes = self.points['class'].to_numpy(copy=True)

        # Render in viewer
        if self.viewer_is_ready():
            self.viewer.clear()
            self.viewer.load(self.points[['x', 'y', 'z']])
            self.viewer.set(point_size=self.point_size, selected=[])
            self.update_attributes()
            if cam_persp is not None and preserve_camera:
                self.set_perspective(cam_persp)
        else:
            self.render(self.showing, preserve_camera=preserve_camera)

        return True

    def highlight(self, mask=None, indices=None):
        """
        Set the selected points to be highlighted in the viewer (if they are rendered).
        """
        if mask is None and indices is None:
            return
        if indices is not None:
            mask = self.select(indices=indices, highlighted=False)
        if self.viewer_is_ready():
            indices = self.get_relative_indices(mask)
            self.viewer.set(selected=indices)

    def get_perspective(self):
        """
        This function captures the current perspective of the viewer and returns its parameters so that the user
        can return to this perspective later or use it in a rendering sequence.
        :return: Perspective parameters (lookat[0], lookat[1], lookat[2], phi, theta, r).
        """
        return self.camera_controller.get_perspective()

    def set_perspective(self, p):
        """
        This method allows the user to set the camera perspective manually in the pptk viewer.
        """
        return self.camera_controller.set_perspective(p)

    def save_camera(self, name='default'):
        """Save current camera perspective."""
        return self.camera_controller.save_camera(name)

    def restore_camera(self, name='default'):
        """Restore camera perspective."""
        return self.camera_controller.restore_camera(name)

    def select(self, indices=None, highlighted=True, showing=False, classes=None, data=None, intensity=None,
               red=None, green=None, blue=None, compliment=False, invert=False):
        """
        Return a mask indicating the selected points. Select points based on a number of methods including by
        index, by color, by class, by intensity, or by which points are rendered or highlighted in the viewer.
        If multiple selection methods are used at once, return the intersection of the selections.
        If compliment is True, then return everything EXCEPT the selected points.
        :param indices: List of point indices relative to the entire point cloud.
        :param highlighted: If True, then only grab the points currently highlighted in the viewer.
        :param showing: If True, then only grab points that are currently rendered.
        :param classes: Some list or iterable range from 0 to 8.
        :param data: Some list or iterable range from 0 to 255.
        :param intensity: Some list or iterable range from 0 to 255.
        :param red: Some list or iterable range from 0 to 255.
        :param green: Some list or iterable range from 0 to 255.
        :param blue: Some list or iterable range from 0 to 255.
        :param compliment: If True, return a mask indicating the NON-selected points.
        :return: Boolean mask indicating which points are selected relative to the full set.
        """
        if 'r' not in self.points:
            red, green, blue = None, None, None

        mask = Mask(len(self.points), True)
        cur_mask = Mask(len(self.points), False)
        if indices is not None and len(indices):
            mask.setr(indices)
        if highlighted:
            cur_mask = self.get_highlighted_mask(invert=invert)
            if cur_mask.count():
                mask.intersection(cur_mask.bools)
        if showing:
            mask.intersection(self.showing.bools)
        if classes is not None:
            cur_mask.false()
            for c in classes:
                cur_mask.union(self.points['class'] == c)
            mask.intersection(cur_mask.bools)
        if data is not None:
            cur_mask.false()
            for d in data:
                cur_mask.union(self.points['user_data'] == d)
            mask.intersection(cur_mask.bools)
        if intensity is not None:
            cur_mask.false()
            for i in intensity:
                cur_mask.union(self.points['intensity'] == i)
            mask.intersection(cur_mask.bools)
        if red is not None:
            cur_mask.false()
            for r in red:
                cur_mask.union(self.points['r'] == r)
            mask.intersection(cur_mask.bools)
        if green is not None:
            cur_mask.false()
            for g in green:
                cur_mask.union(self.points['g'] == g)
            mask.intersection(cur_mask.bools)
        if blue is not None:
            cur_mask.false()
            for b in blue:
                cur_mask.union(self.points['b'] == b)
            mask.intersection(cur_mask.bools)
        if compliment:
            mask.compliment()
        return mask

    def classify(self, cls, overwrite=False, mask=None, preserve_camera=True):
        """
        Set the class of the currently selected points to cls. If the class is already set, then only
        overwrite the old value if "overwrite" is True.
        """
        sel_indices = []
        if self.viewer_is_ready():
            try:
                sel = self.viewer.get('selected')
                if sel is not None and len(sel) > 0:
                    sel_indices = sel.copy() if hasattr(sel, 'copy') else list(sel)
            except Exception:
                sel_indices = []

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
            self.viewer.set(selected=[])
            if not preserve_camera:
                self.render(showing=True, preserve_camera=False)
        elif self.render_flag and self.viewer is not None:
            self.render(showing=True, preserve_camera=preserve_camera)

    def undo(self):
        """
        Revert the last classification action and restore the active selection in the viewer.
        """
        success, message, action = self.history_manager.undo(self.points)
        if not success:
            return False, message

        if self.viewer_is_ready():
            self.update_attributes()
            sel_indices = action.get('selection_indices', [])
            if sel_indices is not None and len(sel_indices) > 0:
                self.viewer.set(selected=sel_indices)
            else:
                self.highlight(indices=action['indices'])

        return True, message

    def redo(self):
        """
        Re-apply the last undone action.
        """
        success, message, action = self.history_manager.redo(self.points)
        if not success:
            return False, message

        if self.viewer_is_ready():
            self.update_attributes()
            self.viewer.set(selected=[])

        return True, message


    def center(self):
        """Shift the origin of the point cloud to its centroid."""
        PointCloudTransforms.center(self.points)

    def reset_origin(self):
        """Shift the origin of the point cloud to the minimum of the point cloud."""
        PointCloudTransforms.reset_origin(self.points)

    def subsample(self, n=10000000, percent=1.0):
        """Return a random sample boolean mask of the point cloud."""
        return PointCloudTransforms.subsample(len(self.points), n=n, percent=percent)

    def add_points(self, points):
        """
        Append a pandas dataframe of points to the current list of points. The pandas DataFrame
        must have 'x' and 'y' columns, and cannot have any abnormal columns in it.
        """
        if not isinstance(points, pd.DataFrame):
            print('Error: points must be in the form of a pandas DataFrame. Cannot append.')
            return
        if 'x' not in points.columns or 'y' not in points.columns:
            print('Error: missing x and/or y column data. Cannot append.')
            return
        for c in points.columns:
            if c not in self.points.columns:
                print('Error: unknown column', c, 'in points. Cannot append.')
                return
        self.points = pd.concat([self.points, points], ignore_index=True, sort=False).fillna(0)

    def slice(self, points=None, position=1.75, thickness=0.2, axis=2):
        """Take a planar slice of some thickness out of the data."""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.slice(points, position=position, thickness=thickness, axis=axis)

    def in_box_2d(self, box, points=None):
        """Return a boolean mask indicating which points are within the given 2D bounding box (xy plane)"""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y']].values
        return SpatialQueries.in_box_2d(box, points)

    @staticmethod
    def make_box_from_point(point, delta):
        """Make a square bounding box with center at the given point and side lengths 2*delta"""
        return SpatialQueries.make_box_from_point(point, delta)


    def get_points_within(self, delta, point=None, return_mask=False, return_z=False, proportion=1.0):
        """
        Returns all the points within delta of the given point. Z-axis is not considered in distance calculation.
        If point is None, then use the currently highlighted point as the query point. If multiple points are currently
        highlighted, then use their average as the query point.
        """
        if proportion < 1.0:
            choice = np.random.choice(len(self), int(len(self) * proportion))
            points = self.points.iloc[choice][['x', 'y']]
            if return_mask:
                print(
                    'From get_points_within: Doesn\'t make sense to return mask when proportion < 1.0')
                return []
        else:
            points = self.points[['x', 'y']]
        if point is None:
            selected = self.get_highlighted_mask()
            point = np.average(
                self.points.loc[selected.bools][['x', 'y']], axis=0)
        x, y = point[:2]
        keep = np.ones(len(points), dtype=bool)
        keep[points['x'] < x - delta] = False
        keep[points['x'] > x + delta] = False
        keep[points['y'] < y - delta] = False
        keep[points['y'] > y + delta] = False
        if return_mask:
            return keep
        elif return_z:
            return points.loc[keep][['x', 'y', 'z']].values
        else:
            return points.loc[keep][['x', 'y']].values

    def distance_to_line(self, line, point):
        """Calculate the distance between a given point and a given line"""
        return SpatialQueries.distance_to_line(line, point)

    def get_points_near_line(self, line, delta=0.01):
        """Return indices of points within delta of the given line"""
        pts = self.points[['x', 'y']].values
        dists = np.array([SpatialQueries.distance_to_line(line, p) for p in pts])
        return np.where(dists < delta)[0]

    def rounding_filter(self, points=None, round=0.02):
        """Round point locations to nearest round_val and return unique coordinates."""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.rounding_filter(points, round_val=round)

    def radial_filter(self, points=None, threshold=10, radius=0.05):
        """Verify each point has at least threshold neighbors within radius."""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.radial_filter(points, threshold=threshold, radius=radius)

    def move(self, init, last):
        self.points.loc[self.points['class'] == init, ['class']] = last

    def fix(self, init, last):
        for i in range(last, init, -1):
            print(str(i))
            self.points.loc[self.points['class'] == i, ['class']] = i+1
        self.render()

    def labelIsEmpty(self, label):
        if(len(self.points.loc[self.points['class'] == label, ['class']]) > 0):
            print("Label: " + str(label) + " has data")
        else:
            print("Label: " + str(label) + " is empty.")

    def neighbors(self, k=100, highlight=True):
        """
        Find the centroid of the currently highlighted points and return a Mask indicating which points are neighbors.
        """
        mask = self.select(showing=False, highlighted=True)
        if not mask.count() or mask.count() == len(self.points):
            print('No points were selected')
            return

        points = self.points.loc[mask.bools][['x', 'y', 'z']]
        if len(points) == 1:
            query = points
        else:
            query = np.average(points, axis=0)

        if self.index is None:
            self.index = knn.Query()
            self.index.pptk(
                self.points.loc[self.showing.bools][['x', 'y', 'z']].values)

        neighbors = self.index.neighbors(query, k)
        mask.setr(neighbors)
        if highlight:
            self.highlight(mask)
        return mask

    def plane_filter(self, points=None, mesh=0.06, axis=2):
        """Return point count density per slice along axis."""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.plane_filter(points, mesh=mesh, axis=axis)

    def color_groups(self, groups, store=False, render=True):
        """Given a list of lists of indices, color all the points in a given group one random color."""
        labels = np.zeros(len(self.points), dtype=int)
        if not len(groups):
            return []
        elif not isinstance(groups[0], list):
            groups = [groups]

        for indices in groups:
            label = np.random.randint(1, 32)
            if len(indices):
                labels[indices] = label

        if render and self.viewer_is_ready():
            self.viewer.attributes(labels[self.showing.bools])
        if store:
            self.points['user_data'] = labels
        else:
            return labels

    def regularize(self, points=None, mesh=0.02):
        """Downsample point cloud to 1 point per voxel grid of mesh size."""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.regularize(points, mesh=mesh)

    def get_points_in_bounds(self, bounds, points=None, extra=0.0):
        """Return a boolean mask indicating which points are contained in bounds."""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return SpatialQueries.get_points_in_bounds(bounds, points, extra=extra)

    def auto_align_bound_box_method(self, tolerance=0.1, max_points=10000, thickness=0.2):
        """Incrementally rotates point cloud to minimize bounding box exterior points."""
        points = self.points[['x', 'y']].values
        if max_points < len(points):
            subsample = np.random.choice(len(points), max_points)
            points = points[subsample]
        best_cost, best_angle = np.inf, 0.0
        for i in range(int(90. / tolerance)):
            bounds = [points.min(axis=0), points.max(axis=0)]
            bounds[0] += thickness
            bounds[1] -= thickness
            inbox = self.in_box_2d(bounds, points)
            cost = inbox.sum()
            if cost < best_cost:
                best_cost = cost
                best_angle = i * tolerance
            points = self.rotate(points, tolerance)
        if best_angle:
            self.points[['x', 'y']] = self.rotate(degrees=best_angle)
            self.render(showing=True)
        return best_angle

    def auto_align_hough_line_method(self, tolerance=0.1, max_points=100000):
        """Align point cloud with x and y axes using Hough line detection."""
        points = self.points[['x', 'y']].values
        if max_points < len(points):
            subsample = np.random.choice(len(points), max_points)
            points = points[subsample]
        votes, _, tol, center = self.hough_lines(points, theta_precision=5.0, angle_range=90)
        angle = np.degrees(list(votes.keys())[np.argmax(list(votes.values()))][1] * tol + center)
        votes, _, tol, center = self.hough_lines(points, theta_precision=tol, angle_range=5, theta_center=angle)
        angle = np.degrees(list(votes.keys())[np.argmax(list(votes.values()))][1] * tol + center)
        print('rotating', angle, 'degrees')
        self.points[['x', 'y']] = self.rotate(degrees=angle)
        self.render(showing=True)

    @staticmethod
    def hough_lines(points, theta_precision=0.5, angle_range=90, rho_precision=0.02, theta_center=0.0):
        """Hough line transform on 2D coordinates."""
        return PointCloudFilters.hough_lines(
            points, theta_precision=theta_precision, angle_range=angle_range,
            rho_precision=rho_precision, theta_center=theta_center
        )

    def hough_circles(self, points, radius=0.05, resolution=0.010):
        """Hough circle detection in xy-planes."""
        points = (points[:, :2] / resolution).astype(int)
        angles = [np.radians(theta) for theta in range(0, 360)]
        displacements = radius * np.array([np.array((np.cos(theta), np.sin(theta))) for theta in angles])
        displacements = np.unique((displacements / resolution).astype(int), axis=0)
        votes = defaultdict(int)
        for point in points:
            for d in displacements:
                votes[tuple(point + d)] += 1
        return votes, radius, resolution

    def hough_squares(self, points, length=0.1, resolution=0.010):
        """Hough square detection in xy-planes."""
        points = (points[:, :2] / resolution).astype(int)
        n = int(length / resolution / 2.)
        displacements = [np.array((x, n)) for x in range(-n, n+1)]
        displacements += [np.array((x, -n)) for x in range(-n, n+1)]
        displacements += [np.array((n, y)) for y in range(-n+1, n)]
        displacements += [np.array((-n, y)) for y in range(-n+1, n)]
        votes = defaultdict(int)
        for point in points:
            for d in displacements:
                votes[tuple(point + d)] += 1
        return votes, length, resolution

    def hough_intersections(self, points, resolution=0.01):
        """Find location of intersecting lines in xy coordinates."""
        votes, rho_precision, theta_precision, theta_center = self.hough_lines(
            points, theta_precision=0.1, rho_precision=resolution)
        n = 100
        best = np.argsort(list(votes.values()))[-n:]
        best_keys = np.array(list(votes.keys()))[best]
        dists, angles = best_keys[:, 0] * rho_precision, best_keys[:, 1] * theta_precision + theta_center
        values = np.array(list(votes.values()))[best]
        best_pair, best_score = None, 0
        for i in range(len(best)):
            for j in range(i, len(best)):
                score = (values[i] + values[j]) * abs(np.sin(angles[i] - angles[j]))
                if score > best_score:
                    best_score = score
                    best_pair = (i, j)
        i, j = best_pair
        theta1, theta2 = angles[i], angles[j]
        rho1, rho2 = dists[i], dists[j]
        m1, m2 = np.tan(theta1 + np.pi / 2.), np.tan(theta2 + np.pi / 2.)
        x1, y1 = rho1 * np.cos(theta1), rho1 * np.sin(theta1)
        x2, y2 = rho2 * np.cos(theta2), rho2 * np.sin(theta2)
        X = ((m1 * x1 - y1) - (m2 * x2 - y2)) / (m1 - m2)
        Y = m1 * (X - x1) + y1
        return X, Y

    def rotate(self, points=None, degrees=0.0, axes=['x', 'y']):
        """Rotate coordinates around the z axis by degrees."""
        if points is None:
            points = self.points.loc[self.showing.bools][axes].values
        return PointCloudTransforms.rotate(points, degrees=degrees)

    def normals(self, points=None, k=100, r=0.35, render=False):
        """Surface normals using PCA."""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        n = PointCloudFilters.estimate_normals(points, k=k, r=r)
        if render and self.viewer_is_ready():
            self.viewer.attributes(n)
        return n

    def curvature(self, points=None, k=100, r=0.35):
        """Surface curvature using PCA eigenvalues."""
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y', 'z']].values
        return PointCloudFilters.estimate_curvature(points, k=k, r=r)


    # ------------------ AI Assisted Tools (Experimental) ------------------
    def ai_auto_ground(self, cell_size=1.0, distance_threshold=0.25, overwrite=False):
        """Fit a 2.5D surface to detect the ground plane across the selection."""
        if not self.viewer_is_ready():
            return False, "Viewer is not ready"

        if not self.has_selection() and not self.is_work_area_active():
            return False, "Select a region or isolate a work area first"

        if self.has_selection():
            mask = self.get_highlighted_mask()
        else:
            mask = Mask(len(self.points), False)
            mask.bools = self.active_roi.bools.copy()

        pts_indices = np.where(mask.bools)[0]
        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values

        success, msg, local_indices = GroundDetector.detect_ground(
            xyz, cell_size=cell_size, distance_threshold=distance_threshold
        )
        if not success:
            return False, msg

        ground_global = pts_indices[local_indices]
        ground_mask = Mask(len(self.points), False)
        ground_mask.bools[ground_global] = True

        self.classify(cls=1, mask=ground_mask, overwrite=overwrite, preserve_camera=True)
        return True, f"Auto Ground: Classified {len(ground_global)}/{len(pts_indices)} points as Suelo"

    def ai_classify_pole(self, height_threshold=12.0, cylinder_radius=0.55, overwrite=False):
        """Segment vertical pole points and classify as Postes BT or Postes MT."""
        if not self.viewer_is_ready():
            return False, "Viewer is not ready"

        if not self.has_selection() and not self.is_work_area_active():
            return False, "Select a pole region or isolate a work area first"

        if self.has_selection():
            mask = self.get_highlighted_mask()
        else:
            mask = Mask(len(self.points), False)
            mask.bools = self.active_roi.bools.copy()

        pts_indices = np.where(mask.bools)[0]
        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values

        success, msg, local_indices, cls_code, height = PoleDetector.detect_pole(
            xyz, height_threshold=height_threshold, cylinder_radius=cylinder_radius
        )
        if not success:
            return False, msg

        pole_global = pts_indices[local_indices]
        pole_mask = Mask(len(self.points), False)
        pole_mask.bools[pole_global] = True

        self.classify(cls=cls_code, mask=pole_mask, overwrite=overwrite, preserve_camera=True)
        cls_name = "Postes MT" if cls_code == 6 else "Postes BT"
        return True, f"Classify Pole: {cls_name} (Height: {height:.2f}m, Isolated {len(pole_global)}/{len(pts_indices)} pts)"

    def ai_grow_cable(self, min_clearance=1.5, overwrite=False):
        """Segment overhead cables by local elevation and geometric linearity."""
        if not self.viewer_is_ready():
            return False, "Viewer is not ready"

        if not self.has_selection() and not self.is_work_area_active():
            return False, "Select points on cables or isolate a work area first"

        if self.has_selection():
            mask = self.get_highlighted_mask()
        else:
            mask = Mask(len(self.points), False)
            mask.bools = self.active_roi.bools.copy()

        pts_indices = np.where(mask.bools)[0]
        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values

        success, msg, local_indices = CableDetector.detect_cables(
            xyz, min_clearance=min_clearance
        )
        if not success:
            return False, msg

        cable_global = pts_indices[local_indices]
        cable_mask = Mask(len(self.points), False)
        cable_mask.bools[cable_global] = True

        self.classify(cls=5, mask=cable_mask, overwrite=overwrite, preserve_camera=True)
        return True, f"Grow Cable: Classified {len(cable_global)}/{len(pts_indices)} points as Cables BT"

    def ai_classify_veg(self, min_clearance=0.35, overwrite=False):
        """Segment vegetation based on 3D volumetric scattering."""
        if not self.viewer_is_ready():
            return False, "Viewer is not ready"

        if not self.has_selection() and not self.is_work_area_active():
            return False, "Select a vegetation region or isolate a work area first"

        if self.has_selection():
            mask = self.get_highlighted_mask()
        else:
            mask = Mask(len(self.points), False)
            mask.bools = self.active_roi.bools.copy()

        pts_indices = np.where(mask.bools)[0]
        current_classes = self.points.loc[pts_indices, 'class'].values
        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values

        success, msg, local_indices = VegetationDetector.detect_vegetation(
            xyz, current_classes=current_classes, min_clearance=min_clearance, overwrite=overwrite
        )
        if not success:
            return False, msg

        veg_global = pts_indices[local_indices]
        veg_mask = Mask(len(self.points), False)
        veg_mask.bools[veg_global] = True

        self.classify(cls=2, mask=veg_mask, overwrite=overwrite, preserve_camera=True)
        return True, f"Classify Veg: Classified {len(veg_global)}/{len(pts_indices)} points as Vegetación"


