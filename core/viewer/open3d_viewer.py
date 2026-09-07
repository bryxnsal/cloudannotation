"""
Open3dViewerAdapter: Adapter for 3D point cloud visualization and interaction using Open3D.
Runs an interactive VisualizerWithVertexSelection window.
"""
import threading
import time
import numpy as np
import open3d as o3d
from core.viewer.base_viewer import BaseViewerAdapter


# Default palette for class-based visualization when RGB is absent or when classes are shown
DEFAULT_PALETTE = np.array([
    [0.7, 0.7, 0.7],  # 0: Unclassified (gray)
    [0.55, 0.27, 0.07], # 1: Ground (brown)
    [0.13, 0.55, 0.13], # 2: Vegetation (green)
    [0.85, 0.65, 0.13], # 3: Buildings (golden/yellow)
    [0.8, 0.2, 0.2],   # 4: Postes BT (red)
    [0.2, 0.6, 0.8],   # 5: Cables BT (cyan/blue)
    [0.9, 0.5, 0.1],   # 6: Postes MT (orange)
    [0.1, 0.4, 0.9],   # 7: Cables MT (blue)
    [0.6, 0.1, 0.8],   # 8: Postes AT (purple)
    [0.1, 0.8, 0.8],   # 9: Cables AT (teal)
    [0.9, 0.9, 0.2],   # 10: Anuncios (yellow)
    [0.4, 0.3, 0.2],   # 11: Escombros
    [0.5, 0.5, 0.5],   # 12: Andamios
    [0.7, 0.4, 0.1],   # 13: Escaleras
    [0.8, 0.3, 0.2],   # 14: Ladrillos
    [1.0, 0.0, 1.0],   # 15: Trabajos electricos MT (magenta)
], dtype=np.float64)


class Open3dViewerAdapter(BaseViewerAdapter):
    """
    Manages rendering, interaction, point picking and camera parameters using Open3D Visualizer.
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
        # Convert pptk-like float (e.g. 0.01) to pixel scale if very small, or use directly
        if size < 0.1:
            pixel_size = max(1.0, size * 300.0)
        else:
            pixel_size = float(size)

        self.point_size = pixel_size
        if self.is_ready():
            try:
                render_opt = self.vis.get_render_option()
                if render_opt:
                    render_opt.point_size = float(self.point_size)
                    return True
            except Exception as e:
                print("Open3dViewer: Error setting point size:", e)
        return False

    def _get_colors(self, points_df, mask):
        """Compute Nx3 float RGB colors in [0, 1] range based on df columns."""
        mask_indices = mask[:] if hasattr(mask, '__getitem__') else mask
        num_pts = int(np.sum(mask_indices))
        if num_pts == 0:
            return np.zeros((0, 3), dtype=np.float64)

        if 'r' in points_df.columns and 'g' in points_df.columns and 'b' in points_df.columns:
            rgb = points_df.loc[mask_indices, ['r', 'g', 'b']].to_numpy(dtype=np.float64)
            if rgb.max() > 1.0:
                rgb /= 255.0
            return rgb

        if 'class' in points_df.columns:
            classes = points_df.loc[mask_indices, 'class'].to_numpy(dtype=int)
            colors = np.zeros((num_pts, 3), dtype=np.float64)
            palette_len = len(DEFAULT_PALETTE)
            for idx, c in enumerate(classes):
                colors[idx] = DEFAULT_PALETTE[c % palette_len]
            return colors

        # Default white/light gray
        return np.full((num_pts, 3), 0.8, dtype=np.float64)

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
        """Load or replace point cloud geometry in Open3D viewport."""
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
            self._start_visualizer(xyz, rgb)
            return True

        with self._lock:
            try:
                # Capture camera before replacing geometry
                view_ctrl = self.vis.get_view_control()
                saved_cam = None
                if preserve_camera and view_ctrl:
                    saved_cam = view_ctrl.convert_to_pinhole_camera_parameters()

                # Update Open3D PointCloud object
                self.pcd.points = o3d.utility.Vector3dVector(xyz)
                self.pcd.colors = o3d.utility.Vector3dVector(rgb)
                self.vis.update_geometry(self.pcd)

                # Restore camera if captured
                if preserve_camera and saved_cam and view_ctrl:
                    view_ctrl.convert_from_pinhole_camera_parameters(saved_cam, allow_arbitrary=True)

                render_opt = self.vis.get_render_option()
                if render_opt:
                    render_opt.point_size = float(self.point_size)

                return True
            except Exception as e:
                print("Open3dViewer: Error rendering geometry:", e)
                return False

    def _start_visualizer(self, initial_xyz, initial_rgb):
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
                        if not alive:
                            break
                    time.sleep(0.016)  # ~60 FPS polling

            except Exception as e:
                print("Open3dViewer: Visualizer loop error:", e)
            finally:
                self._is_running = False
                ready_event.set()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
        ready_event.wait(timeout=3.0)

    def get_selected_indices(self) -> list:
        """Return list of point indices picked via Open3D selection tool."""
        if not self.is_ready():
            return []
        with self._lock:
            try:
                picked = self.vis.get_picked_points()
                if picked:
                    return [int(p.index) for p in picked]
                return []
            except Exception as e:
                return []

    def set_selected_indices(self, indices: list) -> bool:
        """Clear or highlight picked points."""
        if not self.is_ready():
            return False
        with self._lock:
            try:
                self.vis.clear_picked_points()
                if indices and hasattr(self.vis, 'add_picked_points'):
                    self.vis.add_picked_points(indices)
                return True
            except Exception:
                return False
