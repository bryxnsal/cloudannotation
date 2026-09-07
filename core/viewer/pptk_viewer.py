"""
PptkViewerAdapter: Encapsulates all interactions with the PPTK 3D point cloud viewer.
"""
import pptk
import numpy as np

class PptkViewerAdapter:
    """
    Manages the lifecycle, point loading, attribute mapping and interaction with pptk.viewer.
    """
    def __init__(self, camera_controller=None):
        self.viewer = None
        self.camera_controller = camera_controller
        self.point_size = 0.01

    def is_ready(self):
        """Return True if pptk viewer process is alive and responsive."""
        if self.viewer is None:
            return False
        try:
            self.viewer.get('lookat')
            return True
        except Exception:
            return False

    def close(self):
        """Close viewer process gracefully."""
        if self.is_ready():
            try:
                self.viewer.close()
            except Exception:
                pass
        self.viewer = None

    def set_point_size(self, size):
        """Update point rendering size dynamically."""
        self.point_size = float(size)
        if self.is_ready():
            try:
                self.viewer.set(point_size=self.point_size)
                return True
            except Exception as e:
                print("Error setting point size in viewer:", e)
        return False

    def update_attributes(self, points_df, mask):
        """
        Update colors, classification labels, user_data, and intensity on currently loaded geometry.
        """
        if not self.is_ready() or points_df is None or mask is None:
            return False

        try:
            mask_indices = mask[:] if hasattr(mask, '__getitem__') else mask
            if 'r' in points_df.columns:
                scale = 255.0
                colors = points_df.loc[mask_indices, ['r', 'g', 'b']] / scale
                classes = points_df.loc[mask_indices, 'class']
                if 'user_data' in points_df.columns and 'intensity' in points_df.columns:
                    self.viewer.attributes(
                        colors, classes,
                        points_df.loc[mask_indices, 'user_data'],
                        points_df.loc[mask_indices, 'intensity']
                    )
                elif 'user_data' in points_df.columns:
                    self.viewer.attributes(
                        colors, classes,
                        points_df.loc[mask_indices, 'user_data']
                    )
                elif 'intensity' in points_df.columns:
                    self.viewer.attributes(
                        colors, classes,
                        points_df.loc[mask_indices, 'intensity']
                    )
                else:
                    self.viewer.attributes(colors, classes)
            else:
                self.viewer.attributes(points_df.loc[mask_indices, 'class'])
            return True
        except Exception as e:
            print("Error updating attributes in viewer:", e)
            return False

    def render(self, points_df, mask, preserve_camera=True):
        """
        Render selected points into viewer, preserving camera orientation when requested.
        """
        if points_df is None or mask is None:
            return False

        mask_indices = mask[:] if hasattr(mask, '__getitem__') else mask
        num_points = int(np.sum(mask_indices))
        if num_points == 0:
            return False

        # 1. Capture camera if requested
        cam_persp = None
        if preserve_camera and self.camera_controller and self.is_ready():
            cam_persp = self.camera_controller.get_perspective()

        # 2. Load geometry into pptk
        xyz = points_df.loc[mask_indices, ['x', 'y', 'z']]
        if self.is_ready():
            self.viewer.clear()
            self.viewer.load(xyz)
        else:
            self.viewer = pptk.viewer(xyz)

        self.viewer.set(point_size=self.point_size, selected=[])
        self.update_attributes(points_df, mask)

        # 3. Restore camera perspective
        if cam_persp is not None and preserve_camera and self.camera_controller:
            total_pts = len(points_df)
            if num_points < total_pts and num_points > 0:
                adjusted = self.camera_controller.compute_anchor_perspective(cam_persp, xyz.to_numpy())
                self.camera_controller.set_perspective(adjusted)
            else:
                self.camera_controller.set_perspective(cam_persp)

        return True

    def get_selected_indices(self):
        """Return indices currently selected via Ctrl+Click in the viewer."""
        if not self.is_ready():
            return []
        try:
            sel = self.viewer.get('selected')
            return [] if sel is None else sel
        except Exception:
            return []

    def set_selected_indices(self, indices):
        """Highlight given relative indices in viewer."""
        if self.is_ready():
            try:
                self.viewer.set(selected=indices if indices is not None else [])
                return True
            except Exception as e:
                print("Error setting selection in viewer:", e)
        return False
