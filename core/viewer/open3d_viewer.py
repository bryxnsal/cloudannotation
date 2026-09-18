"""
Open3dViewerAdapter: Adapter for 3D point cloud visualization and interaction using Open3D.
Runs an interactive VisualizerWithVertexSelection window.
"""
import threading
import time
import numpy as np
import open3d as o3d
from core.viewer.base_viewer import BaseViewerAdapter


# Default palette matching standard PPTK colormapping behavior for classes
def _get_class_colormap(classes: np.ndarray, max_label: int = 25) -> np.ndarray:
    """
    Generate distinct RGB colors in [0, 1] for class IDs, identical to PPTK scalar colormap.
    Class 0 (unclassified) is assigned neutral gray [0.7, 0.7, 0.7].
    Classes >= 1 are mapped across the standard colormap spectrum.
    """
    try:
        import matplotlib.pyplot as plt
        cmap = plt.get_cmap('tab20')
        palette = np.array([cmap(i)[:3] for i in range(20)], dtype=np.float64)
    except Exception:
        palette = np.array([
            [0.12, 0.46, 0.70], [0.68, 0.78, 0.90], [1.00, 0.49, 0.05], [1.00, 0.73, 0.47],
            [0.17, 0.62, 0.17], [0.59, 0.87, 0.54], [0.83, 0.15, 0.15], [1.00, 0.59, 0.58],
            [0.58, 0.40, 0.74], [0.77, 0.69, 0.83], [0.54, 0.33, 0.29], [0.77, 0.61, 0.58],
            [0.89, 0.46, 0.76], [0.96, 0.71, 0.82], [0.49, 0.49, 0.49], [0.78, 0.78, 0.78],
            [0.73, 0.74, 0.13], [0.85, 0.86, 0.54], [0.09, 0.74, 0.81], [0.61, 0.85, 0.89],
        ], dtype=np.float64)

    num_pts = len(classes)
    colors = np.zeros((num_pts, 3), dtype=np.float64)

    # Base neutral color for class 0 (unclassified)
    is_zero = (classes == 0)
    colors[is_zero] = [0.7, 0.7, 0.7]

    non_zero = ~is_zero
    if np.any(non_zero):
        c_indices = (classes[non_zero].astype(int) - 1) % len(palette)
        colors[non_zero] = palette[c_indices]

    return colors


class Open3dViewerAdapter(BaseViewerAdapter):
    """
    Manages rendering, interaction, point picking and camera parameters using Open3D Visualizer.
    Provides 100% functional parity with PPTK viewer.
    """
    def __init__(self, camera_controller=None):
        super().__init__(camera_controller=camera_controller)
        self.vis = None
        self.pcd = None
        self.point_size = 3.0  # Open3D point sizes are typically pixel-based (1.0 to 10.0)
        self._is_running = False
        self._thread = None
        self._lock = threading.Lock()
        self._picked_indices = []
        self._saved_view_params = None

    def is_ready(self) -> bool:
        """Return True if visualizer window is created and running."""
        with self._lock:
            return self._is_running and (self.vis is not None)

    def close(self):
        """Close Open3D visualizer gracefully."""
        self._is_running = False
        with self._lock:
            if self.vis is not None:
                try:
                    self.vis.destroy_window()
                except Exception:
                    pass
                self.vis = None
                self.pcd = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def set_point_size(self, size: float) -> bool:
        """Update point size dynamically."""
        if size < 0.1:
            pixel_size = max(1.0, size * 300.0)
        else:
            pixel_size = float(size)

        self.point_size = pixel_size
        if self.is_ready():
            with self._lock:
                try:
                    render_opt = self.vis.get_render_option()
                    if render_opt:
                        render_opt.point_size = float(self.point_size)
                        return True
                except Exception as e:
                    print("Open3dViewer: Error setting point size:", e)
        return False

    def _get_colors(self, points_df, mask):
        """
        Compute Nx3 float RGB colors in [0, 1] range matching PPTK attribute display.
        If classes are present and any point is classified, display categorical class colormap.
        If class is 0 across all points and real RGB channels exist, display natural RGB.
        """
        mask_indices = mask[:] if hasattr(mask, '__getitem__') else mask
        num_pts = int(np.sum(mask_indices))
        if num_pts == 0:
            return np.zeros((0, 3), dtype=np.float64)

        has_classes = 'class' in points_df.columns
        if has_classes:
            classes = points_df.loc[mask_indices, 'class'].to_numpy(dtype=int)
            # If any points are classified or user is annotating, prioritize class colormap
            if np.any(classes > 0) or not ('r' in points_df.columns and 'g' in points_df.columns and 'b' in points_df.columns):
                return _get_class_colormap(classes)

        # Fallback to direct RGB if classes are not present or all 0
        if 'r' in points_df.columns and 'g' in points_df.columns and 'b' in points_df.columns:
            rgb = points_df.loc[mask_indices, ['r', 'g', 'b']].to_numpy(dtype=np.float64)
            if rgb.max() > 1.0:
                rgb /= 255.0
            return rgb

        if has_classes:
            classes = points_df.loc[mask_indices, 'class'].to_numpy(dtype=int)
            return _get_class_colormap(classes)

        return np.full((num_pts, 3), 0.7, dtype=np.float64)

    def update_attributes(self, points_df, mask) -> bool:
        """Update colors of the currently displayed point cloud."""
        if not self.is_ready() or points_df is None or mask is None:
            return False

        with self._lock:
            try:
                new_colors = self._get_colors(points_df, mask)
                if self.pcd is not None and len(new_colors) == len(self.pcd.points):
                    self.pcd.colors = o3d.utility.Vector3dVector(new_colors)
                    self.vis.update_geometry(self.pcd)
                    return True
            except Exception as e:
                print("Open3dViewer: Error updating attributes:", e)
        return False

    def render(self, points_df, mask, preserve_camera: bool = True) -> bool:
        """
        Load or replace point cloud geometry in Open3D viewport.
        Properly handles changing point counts (for Multi, Select, ROI) by recreating geometry buffers.
        """
        if points_df is None or mask is None:
            return False

        mask_indices = mask[:] if hasattr(mask, '__getitem__') else mask
        num_points = int(np.sum(mask_indices))
        if num_points == 0:
            return False

        xyz = points_df.loc[mask_indices, ['x', 'y', 'z']].to_numpy(dtype=np.float64)
        rgb = self._get_colors(points_df, mask)

        # Initialize visualizer window if not already active
        if not self.is_ready():
            initial_cam = self.get_camera_parameters() if preserve_camera else None
            self._start_visualizer(xyz, rgb, initial_camera_params=initial_cam)
            return True

        with self._lock:
            try:
                # Capture camera before replacing geometry
                view_ctrl = self.vis.get_view_control()
                saved_cam = None
                if preserve_camera and view_ctrl:
                    saved_cam = view_ctrl.convert_to_pinhole_camera_parameters()

                curr_len = len(self.pcd.points) if self.pcd is not None else 0

                if curr_len != num_points:
                    # Point count changed (e.g. Multi, Select ROI, All)
                    # Open3D requires removing and re-adding geometry to resize vertex buffers
                    if self.pcd is not None:
                        self.vis.remove_geometry(self.pcd, reset_bounding_box=False)

                    new_pcd = o3d.geometry.PointCloud()
                    new_pcd.points = o3d.utility.Vector3dVector(xyz)
                    new_pcd.colors = o3d.utility.Vector3dVector(rgb)
                    self.pcd = new_pcd
                    self.vis.add_geometry(self.pcd, reset_bounding_box=False)
                else:
                    # In-place update when point count is identical
                    self.pcd.points = o3d.utility.Vector3dVector(xyz)
                    self.pcd.colors = o3d.utility.Vector3dVector(rgb)
                    self.vis.update_geometry(self.pcd)

                # Restore camera if captured
                if preserve_camera and saved_cam and view_ctrl:
                    view_ctrl.convert_from_pinhole_camera_parameters(saved_cam, allow_arbitrary=True)

                render_opt = self.vis.get_render_option()
                if render_opt:
                    render_opt.point_size = float(self.point_size)

                # Clear picked points on geometry replacement
                self._picked_indices = []

                return True
            except Exception as e:
                print("Open3dViewer: Error rendering geometry:", e)
                return False

    def _start_visualizer(self, initial_xyz, initial_rgb, initial_camera_params=None):
        """Create and launch Open3D visualizer in a background thread."""
        ready_event = threading.Event()

        def _run_loop():
            try:
                vis = o3d.visualization.VisualizerWithVertexSelection()
                vis.create_window(window_name="CloudAnnotation - Open3D Viewer", width=1280, height=800)

                pcd = o3d.geometry.PointCloud()
                pcd.points = o3d.utility.Vector3dVector(initial_xyz)
                pcd.colors = o3d.utility.Vector3dVector(initial_rgb)
                vis.add_geometry(pcd)

                # Restore initial camera perspective if available
                cam_to_apply = initial_camera_params or self._saved_view_params
                if cam_to_apply is not None:
                    try:
                        view_ctrl = vis.get_view_control()
                        if view_ctrl:
                            view_ctrl.convert_from_pinhole_camera_parameters(cam_to_apply, allow_arbitrary=True)
                    except Exception as ce:
                        print("Open3dViewer: Could not restore initial camera:", ce)

                render_opt = vis.get_render_option()
                if render_opt:
                    render_opt.point_size = float(self.point_size)
                    render_opt.background_color = np.array([0.1, 0.1, 0.1])

                with self._lock:
                    self.vis = vis
                    self.pcd = pcd
                    self._is_running = True

                ready_event.set()

                # Event loop
                while self._is_running:
                    with self._lock:
                        if self.vis is None:
                            break
                        alive = self.vis.poll_events()
                        self.vis.update_renderer()

                        # Continuously synchronize picked points
                        try:
                            picked = self.vis.get_picked_points()
                            if picked:
                                self._picked_indices = [int(p.index) for p in picked]
                            else:
                                self._picked_indices = []
                        except Exception:
                            pass

                        if not alive:
                            break
                    time.sleep(0.016)  # ~60 FPS polling

            except Exception as e:
                import traceback
                print("Open3dViewer: Visualizer loop error:", e)
                traceback.print_exc()
            finally:
                self._is_running = False
                ready_event.set()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
        if not ready_event.wait(timeout=5.0):
            print("Open3dViewer: Timeout waiting for visualizer window to initialize.")

    def get_selected_indices(self) -> list:
        """Return list of point indices picked via Open3D selection tool."""
        if not self.is_ready():
            return []
        with self._lock:
            try:
                if self.vis is not None:
                    picked = self.vis.get_picked_points()
                    if picked:
                        self._picked_indices = [int(p.index) for p in picked]
                        return list(self._picked_indices)
                return list(self._picked_indices)
            except Exception as e:
                return list(self._picked_indices)

    def set_selected_indices(self, indices: list) -> bool:
        """Clear or highlight picked points."""
        if not self.is_ready():
            return False
        with self._lock:
            try:
                self._picked_indices = list(indices) if indices else []
                if self.vis is not None:
                    self.vis.clear_picked_points()
                    if indices and hasattr(self.vis, 'add_picked_points'):
                        self.vis.add_picked_points(indices)
                return True
            except Exception:
                return False

    def get_camera_parameters(self):
        """Capture pinhole camera parameters from Open3D view control."""
        if self.is_ready():
            with self._lock:
                try:
                    view_ctrl = self.vis.get_view_control()
                    if view_ctrl:
                        cam = view_ctrl.convert_to_pinhole_camera_parameters()
                        self._saved_view_params = cam
                        return cam
                except Exception as e:
                    print("Open3dViewer: Error capturing camera parameters:", e)
        return self._saved_view_params

    def set_camera_parameters(self, params) -> bool:
        """Restore pinhole camera parameters in Open3D view control."""
        if params is None:
            return False
        self._saved_view_params = params
        if self.is_ready():
            with self._lock:
                try:
                    view_ctrl = self.vis.get_view_control()
                    if view_ctrl:
                        return bool(view_ctrl.convert_from_pinhole_camera_parameters(params, allow_arbitrary=True))
                except Exception as e:
                    print("Open3dViewer: Error setting camera parameters:", e)
        return False
