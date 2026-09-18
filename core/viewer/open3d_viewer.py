"""
Open3dViewerAdapter: Adapter for 3D point cloud visualization and interaction using Open3D.
Runs an interactive VisualizerWithVertexSelection window.
"""
import queue
import threading
import time
import numpy as np
import open3d as o3d
from core.viewer.base_viewer import BaseViewerAdapter


# Jet color palette anchors identical to PPTK default colormap
_PPTK_JET_ANCHORS = np.array([
    [0.0, 0.0, 1.0],  # Blue
    [0.0, 1.0, 1.0],  # Cyan
    [0.0, 1.0, 0.0],  # Green
    [1.0, 1.0, 0.0],  # Yellow
    [1.0, 0.0, 0.0],  # Red
], dtype=np.float64)


def _get_class_colormap(classes: np.ndarray, max_label: int = None) -> np.ndarray:
    """
    Generate distinct RGB colors in [0, 1] for class IDs, identical to PPTK scalar colormap ('jet').
    Class 0 (unclassified) is assigned neutral gray [0.7, 0.7, 0.7].
    Classes >= 1 are mapped across PPTK's default 'jet' colormap scale.
    """
    num_pts = len(classes)
    colors = np.zeros((num_pts, 3), dtype=np.float64)

    is_zero = (classes == 0)
    colors[is_zero] = [0.7, 0.7, 0.7]

    non_zero = ~is_zero
    if np.any(non_zero):
        vals = classes[non_zero].astype(np.float64)
        vmin = 1.0
        vmax = float(max_label) if max_label is not None else float(np.max(vals))
        if vmax <= vmin:
            colors[non_zero] = _PPTK_JET_ANCHORS[0]
        else:
            t = np.clip((vals - vmin) / (vmax - vmin), 0.0, 1.0) * 4.0
            idx = np.clip(np.floor(t).astype(int), 0, 3)
            frac = (t - idx)[:, None]
            colors[non_zero] = (1.0 - frac) * _PPTK_JET_ANCHORS[idx] + frac * _PPTK_JET_ANCHORS[idx + 1]

    return colors



class Open3dViewerAdapter(BaseViewerAdapter):
    """
    Manages rendering, interaction, point picking and camera parameters using Open3D Visualizer.
    Provides 100% functional parity with PPTK viewer.
    All OpenGL mutations are dispatched to the visualizer thread to avoid GLX / WGL BadAccess errors.
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
        self._action_queue = queue.Queue()

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

    def _execute_on_vis_thread(self, func, timeout=5.0):
        """
        Execute a function on the visualizer thread (where OpenGL context is current).
        Blocks until completion and returns the result, or raises on error/timeout.
        """
        if not self.is_ready():
            return None
        res_container = []
        err_container = []
        done_event = threading.Event()

        def wrapper():
            try:
                res_container.append(func())
            except Exception as ex:
                err_container.append(ex)
            finally:
                done_event.set()

        self._action_queue.put(wrapper)
        if done_event.wait(timeout=timeout):
            if err_container:
                raise err_container[0]
            return res_container[0] if res_container else None
        return None

    def set_point_size(self, size: float) -> bool:
        """Update point size dynamically."""
        if size < 0.1:
            pixel_size = max(1.0, size * 300.0)
        else:
            pixel_size = float(size)

        self.point_size = pixel_size
        if self.is_ready():
            def action():
                render_opt = self.vis.get_render_option()
                if render_opt:
                    render_opt.point_size = float(self.point_size)
                    return True
                return False
            try:
                return bool(self._execute_on_vis_thread(action, timeout=1.0))
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

        new_colors = self._get_colors(points_df, mask)

        def action():
            if self.pcd is not None and len(new_colors) == len(self.pcd.points):
                self.pcd.colors = o3d.utility.Vector3dVector(new_colors)
                self.vis.update_geometry(self.pcd)
                return True
            return False

        try:
            return bool(self._execute_on_vis_thread(action, timeout=3.0))
        except Exception as e:
            print("Open3dViewer: Error updating attributes:", e)
            return False

    def render(self, points_df, mask, preserve_camera: bool = True) -> bool:
        """
        Load or replace point cloud geometry in Open3D viewport.
        Properly handles changing point counts (for Multi, Select, ROI) by recreating geometry buffers.
        Executes on the visualizer thread to ensure OpenGL thread safety.
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

        def action():
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
                render_opt.point_color_option = o3d.visualization.PointColorOption.Color
                render_opt.light_on = False

            # Clear picked points on geometry replacement
            self._picked_indices = []
            return True

        try:
            return bool(self._execute_on_vis_thread(action, timeout=5.0))
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

                # Initialize camera: restore previous state or set standard Z-up perspective matching PPTK
                cam_to_apply = initial_camera_params or self._saved_view_params
                view_ctrl = vis.get_view_control()
                if view_ctrl:
                    if cam_to_apply is not None:
                        try:
                            view_ctrl.convert_from_pinhole_camera_parameters(cam_to_apply, allow_arbitrary=True)
                        except Exception as ce:
                            print("Open3dViewer: Could not restore initial camera:", ce)
                    else:
                        # PPTK uses Z-up convention. Set standard Z-up and diagonal perspective in Open3D:
                        try:
                            view_ctrl.set_up([0.0, 0.0, 1.0])
                            view_ctrl.set_front([-1.0, -1.0, 1.0])
                        except Exception:
                            pass

                render_opt = vis.get_render_option()
                if render_opt:
                    render_opt.point_size = float(self.point_size)
                    render_opt.background_color = np.array([0.1, 0.1, 0.1])
                    render_opt.point_color_option = o3d.visualization.PointColorOption.Color
                    render_opt.light_on = False

                with self._lock:
                    self.vis = vis
                    self.pcd = pcd
                    self._is_running = True

                ready_event.set()

                # Event loop
                while self._is_running:
                    # Drain and process queued OpenGL actions on this thread
                    while not self._action_queue.empty():
                        try:
                            action = self._action_queue.get_nowait()
                            action()
                            self._action_queue.task_done()
                        except queue.Empty:
                            break
                        except Exception as qe:
                            print("Open3dViewer: Queued action error:", qe)

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
        with self._lock:
            return list(self._picked_indices)

    def set_selected_indices(self, indices: list) -> bool:
        """Clear or highlight picked points."""
        if not self.is_ready():
            return False

        def action():
            self._picked_indices = list(indices) if indices else []
            if self.vis is not None:
                self.vis.clear_picked_points()
                if indices and hasattr(self.vis, 'add_picked_points'):
                    self.vis.add_picked_points(indices)
            return True

        try:
            return bool(self._execute_on_vis_thread(action, timeout=1.0))
        except Exception:
            return False

    def get_camera_parameters(self):
        """Capture pinhole camera parameters from Open3D view control."""
        if not self.is_ready():
            return self._saved_view_params

        def action():
            view_ctrl = self.vis.get_view_control()
            if view_ctrl:
                cam = view_ctrl.convert_to_pinhole_camera_parameters()
                self._saved_view_params = cam
                return cam
            return None

        try:
            res = self._execute_on_vis_thread(action, timeout=1.0)
            if res is not None:
                return res
        except Exception as e:
            print("Open3dViewer: Error capturing camera parameters:", e)
        return self._saved_view_params

    def set_camera_parameters(self, params) -> bool:
        """Restore pinhole camera parameters in Open3D view control."""
        if params is None:
            return False
        self._saved_view_params = params
        if not self.is_ready():
            return False

        def action():
            view_ctrl = self.vis.get_view_control()
            if view_ctrl:
                return bool(view_ctrl.convert_from_pinhole_camera_parameters(params, allow_arbitrary=True))
            return False

        try:
            return bool(self._execute_on_vis_thread(action, timeout=1.0))
        except Exception as e:
            print("Open3dViewer: Error setting camera parameters:", e)
        return False

