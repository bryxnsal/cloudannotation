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
            total_pts = len(self.points)
            num_rendered = int(np.sum(mask[:]))
            if num_rendered < total_pts and num_rendered > 0:
                rendered_xyz = self.points.loc[mask[:], ['x', 'y', 'z']].to_numpy()
                adjusted_persp = self.camera_controller.compute_anchor_perspective(cam_persp, rendered_xyz)
                self.set_perspective(adjusted_persp)
            else:
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
        """
        Shift the origin of the point cloud to its centroid.
        """
        self.points[['x', 'y', 'z']
                    ] -= np.average(self.points[['x', 'y', 'z']], axis=0)

    def reset_origin(self):
        """
        Shift the origin of the point cloud to the minimum of the point cloud.
        """
        self.points[['x', 'y', 'z']
                    ] -= self.points[['x', 'y', 'z']].values.min(axis=0)

    def subsample(self, n=10000000, percent=1.0):
        """
        Return a random sample of the point cloud.
        """
        threshold = int(percent * len(self.points))
        if n < threshold:
            threshold = n
        if threshold < len(self.points):
            keep = np.zeros(len(self.points), dtype=bool)
            keep[np.random.choice(len(self.points), threshold)] = True
            return keep
        else:
            return np.ones(len(self.points), dtype=bool)

    def add_points(self, points):
        """
        Append a pandas dataframe of points to the current list of points. The pandas DataFrame
        must have 'x' and 'y' columns, and cannot have any abnormal columns in it.
        """
        if not isinstance(points, pd.DataFrame):
            print(
                'Error: points must be in the form of a pandas DataFrame. Cannot append.')
            return
        if 'x' not in points.columns or 'y' not in points.columns:
            print('Error: missing x and/or y column data. Cannot append.')
            return
        for c in points.columns:
            if c not in self.points.columns:
                print('Error: unknown column', c, 'in points. Cannot append.')
                return
        self.points = self.points.append(points)
        self.points = self.points.fillna(0)

    def slice(self, points=None, position=1.75, thickness=0.2, axis=2):
        """
        Take a planar slice of some thickness out of the data. The slice will be axis-aligned.
        :param points: Set of points to take slice from. Default is all currently rendered points.
        :param position: Position along axis to take slice from. Default is 1.75, set for slicing vertical poles above pallets.
        :param thickness: Thickness of slice to take. Default is 0.2 (20 cm).
        :param axis: Axis perpendicular to the slice of data. Must be 0, 1, or 2 (default is 2 (z-axis)).
        """
        if axis == 2:
            str_axis = 'z'
        elif axis == 1:
            str_axis = 'y'
        else:
            str_axis = 'x'
        if points is None:
            points = self.points.loc[self.showing.bools][[
                'x', 'y', 'z']].values
        mask = points[str_axis] > position
        mask[points[str_axis] > position + thickness] = False
        return mask

    def in_box_2d(self, box, points=None):
        """
        Return a boolean mask indicating which points are within the given 2D bounding box (xy plane)
        """
        if points is None:
            points = self.points.loc[self.showing.bools][['x', 'y']].values
        keep = points > np.array(box[0])
        keep[points > np.array(box[1])] = False
        return keep.all(axis=1)

    @ staticmethod
    def make_box_from_point(point, delta):
        """
        Make a square bounding box with center at the given point and side lengths 2*delta
        """
        point = np.array(point)
        return [point - delta, point + delta]

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
        """
        Calculate the distance between a given point and a given line
        :param line: (x1, y1), (x2, y2)
        :param point: (x, y)
        """
        p1, p2 = line
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        if not dx and not dy:
            return np.sqrt(np.square(point[0] - p1[0]) + np.square(point[1] - p1[1]))
        num = np.abs(dy * point[0] - dx * point[1] +
                     p2[0] * p1[1] - p2[1] * p1[0])
        den = np.sqrt(np.square(dx) + np.square(dy))
        return num / den

    def get_points_near_line(self, line, delta=0.01):
        """
        Return a boolean mask indicating which points are within delta of the given line
        :param line: (x1, y1), (x2, y2)
        """
        keep = np.zeros(len(self.points), dtype=bool)
        for i, p in self.points:
            if self.distance_to_line(line, p) < delta:
                keep[i] = True
        return np.arange(len(self.points))[keep]

    def rounding_filter(self, points=None, round=0.02):
        """
        This function rounds the point locations to the nearest "round" (default is 2 cm)
        :return: Unique set of rounded points
        """
        if points is None:
            points = self.points.loc[self.showing.bools][[
                'x', 'y', 'z']].values
        return np.unique(np.round(points / round, decimals=0) * round)

    def radial_filter(self, points=None, threshold=10, radius=0.05):
        """
        This filter checks that each point has at least threshold neighboring points within the given radius.
        A boolean mask is returned indicating which points passed through the filter.
        """
        if points is None:
            points = self.points.loc[self.showing.bools][[
                'x', 'y', 'z']].values
        query = knn.Query()
        query.pptk(points)
        keep = np.ones(len(points), dtype=bool)
        for i, p in enumerate(tqdm(points, desc='Finding neighbors and filtering')):
            neighbors = query.neighbors(p, k=threshold, radius=radius)
            if len(neighbors) < threshold:
                keep[i] = False
        return keep

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
        :param k: Number of neighbors to find.
        :param highlight: If True, then set the currently highlighted points to the neareest k neighbors. Default True.
        :return: Return a copy of the mask indicating which points are neighbors of the selected point(s).
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
        """
        This filter returns the number of counts of points in each slice of the point cloud segmented in
        the given dimension (axis).
        :param points: Set of points to run the method on. By default, run the method on all currently rendered points.
        :param mesh: Mesh size for dividing the point cloud along the given axis.
        :param axis: Axis choice should be 0, 1, or 2 for x, y, and z respectively.
        :return: List of per-point scores or counts indicating how many points share the plane with a given point.
        """
        if points is None:
            points = self.points.loc[self.showing.bools][[
                'x', 'y', 'z']].values

        mesh = np.ones(3) * mesh
        if axis == 0:
            mesh[[1, 2]] = 10000000.0
        elif axis == 1:
            mesh[[0, 2]] = 10000000.0
        elif axis == 2:
            mesh[[0, 1]] = 10000000.0

        vg = VoxelGrid(points, mesh)
        return np.array([vg.counts(vg.index(p)) for p in points])

    def color_groups(self, groups, store=False, render=True):
        """
        Given a list of lists of indices, color all the points in a given group one random color. If store=True, then
        store the coloring scheme in the user_data array.
        """
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
        """
        Regularize the density of the given points using a voxel grid of given mesh size. Simply removes all points
        except one per voxel, so if mesh=0.01, then only 1 point per cubic centimeter will be kept, and all others
        will be thrown away. The first point found in the voxel is kept.
        """
        if points is None:
            points = self.points.loc[self.showing.bools][[
                'x', 'y', 'z']].values
        vg = VoxelGrid(points, mesh_size=mesh)
        keep = np.zeros(len(points), dtype=bool)
        for indices in vg.indices():
            keep[indices[0]] = True
        return keep

    def get_points_in_bounds(self, bounds, points=None, extra=0.0):
        """
        This function returns a boolean mask indicating which points are contained in the given bounds.
        If extra is non-zero, then the extra amount will be added to the x and y dimensions of the bounds in order
        to grab points slightly inside or outside the boundary.
        """
        if points is None:
            points = self.points.loc[self.showing.bools][[
                'x', 'y', 'z']].values
        keep_min = (bounds[0][:2] - extra < points[:, :2]).all(axis=1)
        keep_max = (bounds[1][:2] + extra > points[:, :2]).all(axis=1)
        keep = keep_min
        keep[keep_max == False] = False
        return keep

    def auto_align_bound_box_method(self, tolerance=0.1, max_points=10000, thickness=0.2):
        """
        Automatically align the point cloud with the x and y axes. This method incrementally rotates the point
        cloud and finds its bounding box, then shrinks the bounding box to see how many points become excluded.
        If the point cloud represents a rectangular prism, then when the walls are aligned with the x,y axes, many
        points will fall outside the shrunken bounding box. If the walls are not aligned, then only the corners will
        fall outside of the shrunken bounding box.
        :param tolerance: Align the point cloud to within this tolerance (in degrees)
        :param max_points: Only consider up to max_points points to speed up the calculation
        :param thickness: Thickness of the bounding shell to use
        """
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
        """
        Automatically align the point cloud with the x and y axes. This function uses a Hough transform to find the
        most dominant line in the point cloud and aligns that line with the nearest axis.
        :param tolerance: Align the point cloud to within the given tolerance (in degrees)
        :param max_points: Only consider at most max_points points to speed up computation
        """
        points = self.points[['x', 'y']].values
        if max_points < len(points):
            subsample = np.random.choice(len(points), max_points)
            points = points[subsample]
        # Perform a rough alignment to calculate alignment +/- 5 degrees
        votes, _, tolerance, center = self.hough_lines(
            points, theta_precision=5.0, angle_range=90)
        angle = np.degrees(list(votes.keys())[np.argmax(
            list(votes.values()))][1] * tolerance + center)
        # Perform a fine alignment given the results of the rough alignment
        votes, _, tolerance, center = self.hough_lines(
            points, theta_precision=tolerance, angle_range=5, theta_center=angle)
        angle = np.degrees(list(votes.keys())[np.argmax(
            list(votes.values()))][1] * tolerance + center)
        print('rotating', angle, 'degrees')
        self.points[['x', 'y']] = self.rotate(degrees=angle)
        self.render(showing=True)

    @ staticmethod
    def hough_lines(points, theta_precision=0.5, angle_range=90, rho_precision=0.02, theta_center=0.0):
        """
        This function implements a hough transform for finding lines. The function takes in the representative points,
        converts them to discretized (rho, theta) points and votes into an accumulator called "votes" which is
        returned from the function. The key in "votes" belonging to the largest value represents the most predominant
        line. The key is a discretized (rho, theta), so the actual values are rho * rho_precision and
        theta * theta_precision + theta_center. Only the angles in range(-angle_range, angle_range) will be considered.
        Theta_precision and theta_center are in radians.
        """
        theta_precision, angle_range, theta_center = np.radians(
            theta_precision), np.radians(angle_range), np.radians(theta_center)
        n_steps = int(angle_range / theta_precision)
        theta_idx = [i for i in range(-n_steps, n_steps+1)]
        thetas = np.array(
            [idx * theta_precision + theta_center for idx in theta_idx])
        cosines = np.array([np.cos(theta) for theta in thetas])
        tangents = np.array([np.tan(theta) for theta in thetas])

        # Cast a vote for each line that this point passes through in the given range and precision
        def vote(point):
            # min_distance = b / sqrt(m^2 + 1) = (y - tan(theta) * x) * cos(theta)
            rhos = np.array((point[1] - tangents * point[0])
                            * cosines / rho_precision, dtype=int)
            for rho, idx in zip(rhos, theta_idx):
                votes[(rho, idx)] += 1

        votes = defaultdict(int)
        for point in tqdm(points, desc='Finding lines'):
            vote(point)

        return votes, rho_precision, theta_precision, theta_center

    def hough_circles(self, points, radius=0.05, resolution=0.010):
        """
        This function finds circles of a given radius in the point cloud. It only looks for circles lying in
        xy-planes in the data (no vertical circles).
        """
        # Discretize the points
        points = (points[:, :2] / resolution).astype(int)
        # Define a circle to go around each point
        angles = [np.radians(theta) for theta in range(0, 360)]
        displacements = radius * \
            np.array([np.array((np.cos(theta), np.sin(theta)))
                     for theta in angles])
        # Discretize the circle and only count each discrete location once
        displacements = np.unique(
            (displacements / resolution).astype(int), axis=0)
        # For each point, make a vote for each circle that this point could belong to
        votes = defaultdict(int)
        for point in points:
            for d in displacements:
                votes[tuple(point + d)] += 1
        # In order to get the circle center, find the key corresponding to high voted bin and multiply by resolution
        return votes, radius, resolution

    def hough_squares(self, points, length=0.1, resolution=0.010):
        """
        This function finds squares of a given radius in the point cloud. It only looks for squares lying in
        xy-planes in the data (no vertical squares).
        """
        # Discretize the points
        points = (points[:, :2] / resolution).astype(int)
        # Define a square to go around each point
        n = int(length / resolution / 2.)
        displacements = [np.array((x, n)) for x in range(-n, n+1)]
        displacements += [np.array((x, -n)) for x in range(-n, n+1)]
        displacements += [np.array((n, y)) for y in range(-n+1, n)]
        displacements += [np.array((-n, y)) for y in range(-n+1, n)]
        # For each point, make a vote for each square that this point could belong to
        votes = defaultdict(int)
        for point in points:
            for d in displacements:
                votes[tuple(point + d)] += 1
        # In order to get the square center, find the key corresponding to high voted bin and multiply by resolution
        return votes, length, resolution

    def hough_intersections(self, points, resolution=0.01):
        """
        This function finds the location of two intersecting, non-parallel lines in the point cloud.
        """
        votes, rho_precision, theta_precision, theta_center = self.hough_lines(
            points, theta_precision=0.1, rho_precision=resolution)
        n = 100
        best = np.argsort(list(votes.values()))[-n:]
        best_keys = np.array(list(votes.keys()))[best]
        dists, angles = best_keys[:, 0] * \
            rho_precision, best_keys[:, 1] * theta_precision + theta_center
        values = np.array(list(votes.values()))[best]
        best_pair, best_score = None, 0
        for i in range(len(best)):
            for j in range(i, len(best)):
                score = (values[i] + values[j]) * \
                    abs(np.sin(angles[i] - angles[j]))
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
        """
        This function takes in a list of points (or uses the currently rendered points) and returns a set of points that
        have been rotated by 'degrees' degrees about the given axis. By default, axis=2, so the points will rotate
        about the z-axis.
        """
        if points is None:
            points = self.points.loc[self.showing.bools][axes].values

        t = np.radians(degrees)
        rot = np.array(((np.cos(t), -np.sin(t)), (np.sin(t), np.cos(t))))
        return np.dot(points, rot)

    def normals(self, points=None, k=100, r=0.35, render=False):
        """
        This function takes in a set of points (or uses the currently rendered points) and calculates the surface
        normals using pptk built-in functions which use PCA method. The number of neighbors (k) or the distance
        scale (r) can be changed to affect the resolution of the computation. If render=True, then the results
        will be rendered upon completion.
        """
        if points is None:
            points = self.points.loc[self.showing.bools][[
                'x', 'y', 'z']].values

        n = np.abs(pptk.estimate_normals(points, k, r))
        if render and self.viewer_is_ready():
            self.viewer.attributes(n)

        return n

    def curvature(self, points=None, k=100, r=0.35):
        """
        This function takes in a set of points (or uses the currently rendered points) and calculates the surface
        curvature using pptk built-in functions which use PCA method. The number of neighbors (k) or the distance
        scale (r) can be changed to affect the resolution of the computation. If render=True, then the results
        will be rendered upon completion.
        """
        if points is None:
            points = self.points.loc[self.showing.bools][[
                'x', 'y', 'z']].values

        eigens = np.abs(pptk.estimate_normals(
            points, k, r, output_eigenvalues=True)[0])
        eigens.sort(axis=1)
        return eigens[:, 0] / eigens.sum(axis=1) * 3.0

    # ------------------ AI Assisted Tools (Experimental) ------------------
    def ai_auto_ground(self, distance_threshold=0.25):
        """
        Detect and classify ground plane using RANSAC planar fitting.
        Applies on selected points if available, or currently showing points.
        """
        if not self.viewer_is_ready():
            return False, "Viewer is not ready"

        if self.has_selection():
            mask = self.get_highlighted_mask()
        elif self.is_work_area_active():
            mask = Mask(len(self.points), False)
            mask.bools = self.active_roi.bools.copy()
        elif self.showing is not None:
            mask = self.showing
        else:
            mask = Mask(len(self.points), True)

        pts_indices = np.where(mask.bools)[0]
        if len(pts_indices) < 100:
            return False, "Not enough points to estimate ground plane"

        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values.astype(np.float64)

        # Focus on lowest 35% height slice for robust ground fitting
        z_min = np.min(xyz[:, 2])
        z_max = np.max(xyz[:, 2])
        z_cutoff = z_min + 0.35 * (z_max - z_min)
        low_idx = np.where(xyz[:, 2] <= z_cutoff)[0]
        if len(low_idx) >= 50:
            fit_xyz = xyz[low_idx]
        else:
            fit_xyz = xyz

    def ai_auto_ground(self, cell_size=1.0, distance_threshold=0.25, overwrite=False):
        """
        Fit a 2.5D surface to detect the ground plane across the selection,
        handling sloped or uneven terrain. Respects user overwrite setting.
        """
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
        if len(pts_indices) < 20:
            return False, "Not enough points selected for ground detection"

        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values

        try:
            xy = xyz[:, :2]
            z = xyz[:, 2]

            # 2.5D cell-based ground elevation estimation
            xy_min = np.min(xy, axis=0)
            gx = np.floor((xy[:, 0] - xy_min[0]) / cell_size).astype(int)
            gy = np.floor((xy[:, 1] - xy_min[1]) / cell_size).astype(int)
            cell_ids = gx + gy * 100000

            unique_cids = np.unique(cell_ids)
            z_ground_map = {}
            for cid in unique_cids:
                c_idx = np.where(cell_ids == cid)[0]
                z_ground_map[cid] = np.percentile(z[c_idx], 8)

            z_ground_local = np.array([z_ground_map[cid] for cid in cell_ids])
            height_above_ground = z - z_ground_local

            ground_local = np.where(height_above_ground <= distance_threshold)[0]
            if len(ground_local) == 0:
                return False, "No ground points detected"

            ground_global = pts_indices[ground_local]
            ground_mask = Mask(len(self.points), False)
            ground_mask.bools[ground_global] = True

            self.classify(cls=1, mask=ground_mask, overwrite=overwrite, preserve_camera=True)
            return True, f"Auto Ground: Classified {len(ground_global)}/{len(pts_indices)} points as Suelo"
        except Exception as e:
            return False, f"Ground detection error: {str(e)}"

    def ai_classify_pole(self, height_threshold=12.0, cylinder_radius=0.55, overwrite=False):
        """
        Segment vertical pole points even in low-density LIDAR scans using continuous
        vertical span voting, neighborhood analysis, and ground base exclusion.
        Respects user overwrite setting.
        """
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
        if len(pts_indices) < 8:
            return False, "Not enough points selected for pole analysis"

        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values

        try:
            z_vals = xyz[:, 2]
            z_min, z_max = np.min(z_vals), np.max(z_vals)
            total_height = z_max - z_min
            if total_height < 1.5:
                return False, f"Selected object height ({total_height:.2f}m) is too short for a pole"

            xy = xyz[:, :2]
            n_pts = len(xyz)

            # Subsample candidates to evaluate centers if selection is huge
            if n_pts > 2000:
                sample_idx = np.random.choice(n_pts, size=2000, replace=False)
            else:
                sample_idx = np.arange(n_pts)

            cand_xy = xy[sample_idx]

            from sklearn.neighbors import NearestNeighbors
            nbrs_2d = NearestNeighbors(radius=cylinder_radius, algorithm='kd_tree').fit(xy)
            indices_list = nbrs_2d.radius_neighbors(cand_xy, return_distance=False)

            best_score = -1.0
            best_center = None
            best_indices = None

            for i, in_radius_idx in enumerate(indices_list):
                if len(in_radius_idx) < 5:
                    continue
                z_subset = z_vals[in_radius_idx]
                span_z = np.max(z_subset) - np.min(z_subset)
                if span_z < 1.5:
                    continue

                # Continuous vertical span score
                score = span_z * np.log1p(len(in_radius_idx))
                if score > best_score:
                    best_score = score
                    best_center = cand_xy[i]
                    best_indices = in_radius_idx

            if best_center is None or len(best_indices) < 5:
                return False, "Could not find a prominent vertical pole axis in selection"

            # Refine pole axis center using median of candidate points
            center_x = np.median(xy[best_indices, 0])
            center_y = np.median(xy[best_indices, 1])

            # Horizontal distance from refined center
            dists = np.sqrt((xy[:, 0] - center_x) ** 2 + (xy[:, 1] - center_y) ** 2)
            pole_local_mask = dists <= cylinder_radius

            # Exclude flat ground points at the very base
            z_surrounding_ground = np.percentile(z_vals[dists > cylinder_radius], 5) if np.sum(dists > cylinder_radius) >= 10 else np.min(z_vals)
            pole_local_mask = pole_local_mask & (z_vals >= (z_surrounding_ground + 0.15))

            pole_global_indices = pts_indices[pole_local_mask]
            if len(pole_global_indices) < 5:
                return False, "Could not isolate enough pole points"

            pole_z = self.points.loc[pole_global_indices, 'z'].values
            pole_height = float(np.max(pole_z) - np.min(pole_z))

            if pole_height > height_threshold:
                cls_name = "Postes MT"
                cls_code = 6
            else:
                cls_name = "Postes BT"
                cls_code = 4

            # Classify ONLY the segmented cylinder points
            pole_mask = Mask(len(self.points), False)
            pole_mask.bools[pole_global_indices] = True

            self.classify(cls=cls_code, mask=pole_mask, overwrite=overwrite, preserve_camera=True)
            return True, f"Classify Pole: {cls_name} (Height: {pole_height:.2f}m, Isolated {len(pole_global_indices)}/{len(pts_indices)} pts)"
        except Exception as e:
            return False, f"Pole detection error: {str(e)}"

    def ai_grow_cable(self, min_clearance=1.5, overwrite=False):
        """
        Segment overhead cables (straight, catenary sag, or multi-cable bundles)
        by estimating local elevation and identifying linear structures in the air.
        Respects user overwrite setting.
        """
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
        if len(pts_indices) < 5:
            return False, "Not enough points selected for cable analysis"

        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values

        try:
            from sklearn.neighbors import NearestNeighbors
            xy = xyz[:, :2]
            z_vals = xyz[:, 2]

            # 2.5D ground surface estimation in 1.5m cells
            cell_size = 1.5
            xy_min = np.min(xy, axis=0)
            gx = np.floor((xy[:, 0] - xy_min[0]) / cell_size).astype(int)
            gy = np.floor((xy[:, 1] - xy_min[1]) / cell_size).astype(int)
            cell_ids = gx + gy * 100000

            unique_cids = np.unique(cell_ids)
            z_ground_map = {cid: np.percentile(z_vals[cell_ids == cid], 8) for cid in unique_cids}
            z_ground_local = np.array([z_ground_map[cid] for cid in cell_ids])
            rel_height = z_vals - z_ground_local

            # Aerial clearance: only consider points elevated above local ground
            total_z_span = np.max(z_vals) - np.min(z_ground_local)
            if total_z_span >= 2.5:
                air_mask = rel_height >= min_clearance
            else:
                air_mask = np.ones(len(xyz), dtype=bool)

            air_indices = np.where(air_mask)[0]
            if len(air_indices) < 4:
                return False, "No points found suspended in the air within selection"

            air_xyz = xyz[air_indices]
            n_air = len(air_xyz)

            k = min(8, n_air - 1)
            nbrs = NearestNeighbors(n_neighbors=k + 1, algorithm='kd_tree').fit(air_xyz)
            _, nn_indices = nbrs.kneighbors(air_xyz)

            is_cable = np.zeros(n_air, dtype=bool)
            for i in range(n_air):
                local_pts = air_xyz[nn_indices[i]]
                cov = np.cov(local_pts, rowvar=False)
                if cov.shape != (3, 3):
                    continue

                eigvals, eigvecs = np.linalg.eigh(cov)
                eigvals = np.maximum(eigvals, 1e-9)
                l1, l2, l3 = eigvals[0], eigvals[1], eigvals[2]

                linearity = (l3 - l2) / l3
                scattering = l1 / l3
                primary_dir = eigvecs[:, 2]
                verticality = abs(primary_dir[2])

                # Cables: Linear (>= 0.45), low 3D scattering (<= 0.12), not purely vertical (<= 0.80)
                if linearity >= 0.45 and scattering <= 0.12 and verticality <= 0.80:
                    is_cable[i] = True

            cable_air_idx = air_indices[is_cable]
            if len(cable_air_idx) == 0:
                return False, "No linear cable structures detected at elevated height"

            cable_global = pts_indices[cable_air_idx]
            cable_mask = Mask(len(self.points), False)
            cable_mask.bools[cable_global] = True

            self.classify(cls=5, mask=cable_mask, overwrite=overwrite, preserve_camera=True)
            return True, f"Grow Cable: Classified {len(cable_global)}/{len(pts_indices)} points as Cables BT"
        except Exception as e:
            return False, f"Cable analysis error: {str(e)}"

    def ai_classify_veg(self, min_clearance=0.35, overwrite=False):
        """
        Segment vegetation (trees, bushes, foliage) based on 3D volumetric scattering
        and local 2.5D elevation above ground, classifying points as Vegetación (cls=2).
        Explicitly protects already labeled cables, poles, and buildings, respecting overwrite.
        """
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
        if len(pts_indices) < 10:
            return False, "Not enough points selected for vegetation analysis"

        # Check existing classes in selection
        current_classes = self.points.loc[pts_indices, 'class'].values

        # Cables and poles that must NEVER be overwritten as foliage even if user selects over them
        PROTECTED_CLASSES = {
            4, 6, 8,            # Postes BT, MT, AT
            5, 7, 9, 21, 22, 23 # Cables BT, MT, AT, MT 1, 2, 3
        }

        xyz = self.points.loc[pts_indices, ['x', 'y', 'z']].values

        try:
            from sklearn.neighbors import NearestNeighbors
            xy = xyz[:, :2]
            z_vals = xyz[:, 2]

            # 2.5D ground surface estimation in 1.0m cells
            cell_size = 1.0
            xy_min = np.min(xy, axis=0)
            gx = np.floor((xy[:, 0] - xy_min[0]) / cell_size).astype(int)
            gy = np.floor((xy[:, 1] - xy_min[1]) / cell_size).astype(int)
            cell_ids = gx + gy * 100000

            unique_cids = np.unique(cell_ids)
            z_ground_map = {cid: np.percentile(z_vals[cell_ids == cid], 8) for cid in unique_cids}
            z_ground_local = np.array([z_ground_map[cid] for cid in cell_ids])
            height_above_ground = z_vals - z_ground_local

            # Filter points above ground clearance
            total_z_span = np.max(z_vals) - np.min(z_ground_local)
            if total_z_span >= 1.5:
                above_ground_mask = height_above_ground >= min_clearance
            else:
                above_ground_mask = np.ones(len(xyz), dtype=bool)

            cand_indices = np.where(above_ground_mask)[0]
            if len(cand_indices) < 5:
                return False, "No elevated points found above ground level in selection"

            cand_xyz = xyz[cand_indices]
            n_cand = len(cand_xyz)

            k = min(8, n_cand - 1)
            nbrs = NearestNeighbors(n_neighbors=k + 1, algorithm='kd_tree').fit(xyz)
            _, nn_indices = nbrs.kneighbors(cand_xyz)

            is_veg = np.zeros(n_cand, dtype=bool)
            for i in range(n_cand):
                orig_idx = cand_indices[i]
                orig_cls = current_classes[orig_idx]

                # If already classified as a cable or pole, protect it completely!
                if orig_cls in PROTECTED_CLASSES:
                    continue

                # If overwrite is False and point is already classified (> 0), don't overwrite
                if not overwrite and orig_cls > 0:
                    continue

                local_pts = xyz[nn_indices[i]]
                cov = np.cov(local_pts, rowvar=False)
                if cov.shape != (3, 3):
                    continue

                eigvals, eigvecs = np.linalg.eigh(cov)
                eigvals = np.maximum(eigvals, 1e-9)
                l1, l2, l3 = eigvals[0], eigvals[1], eigvals[2]

                linearity = (l3 - l2) / l3
                planarity = (l2 - l1) / l3
                scattering = l1 / l3
                primary_dir = eigvecs[:, 2]
                verticality = abs(primary_dir[2])

                # Exclude cables (high linearity, low scattering, horizontal)
                is_cable = (linearity >= 0.60 and scattering <= 0.05 and verticality <= 0.40)
                # Exclude poles (high verticality, high linearity)
                is_pole = (verticality >= 0.70 and linearity >= 0.45)
                # Exclude clean planar walls/roofs
                is_plane = (planarity >= 0.75 and scattering <= 0.04)

                if not is_cable and not is_pole and not is_plane:
                    is_veg[i] = True

            veg_local_idx = cand_indices[is_veg]
            if len(veg_local_idx) == 0:
                return False, "No vegetation patterns detected in selection"

            veg_global = pts_indices[veg_local_idx]
            veg_mask = Mask(len(self.points), False)
            veg_mask.bools[veg_global] = True

            self.classify(cls=2, mask=veg_mask, overwrite=overwrite, preserve_camera=True)
            return True, f"Classify Veg: Classified {len(veg_global)}/{len(pts_indices)} points as Vegetación"
        except Exception as e:
            return False, f"Vegetation analysis error: {str(e)}"

