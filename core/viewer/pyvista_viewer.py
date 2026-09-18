"""
PyvistaViewerAdapter: High-performance 3D point cloud viewer adapter using PyVista and VTK.
Provides 100% parity with PPTK and VisPy:
- Terrain/Turntable camera with +Z as up vector (smooth orbital navigation)
- Ctrl + Left Click rectangle selection (vectorized screen space bounding-box filter)
- Yellow highlights for selected points
- Pure 'jet' scalar colormap for point classification
- Support for millions of points with GPU VTK mappers
- Cross-platform support (Linux, Windows, macOS)
"""
import queue
import threading
import time
import numpy as np

try:
    import pyvista as pv
    import vtk
except ImportError:
    pv = None
    vtk = None

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


class PyvistaViewerAdapter(BaseViewerAdapter):
    """
    Manages 3D point cloud rendering, interaction, selection and camera with PyVista / VTK.
    """
    def __init__(self, camera_controller=None):
        super().__init__(camera_controller=camera_controller)
        self.plotter = None
        self.polydata = None
        self.actor = None
        self.point_size = 3.0  # Pixel size for VTK
        self._is_running = False
        self._thread = None
        self._lock = threading.Lock()
        self._action_queue = queue.Queue()

        self._current_xyz = None
        self._current_colors = None
        self._picked_indices = []
        self._saved_cam_state = None

        # Selection state
        self._is_selecting = False
        self._select_start = None
        self._rect_actor = None
        self._rect_pts = None

    def is_ready(self) -> bool:
        with self._lock:
            return self._is_running and (self.plotter is not None)

    def close(self):
        self._is_running = False
        def close_action():
            if self.plotter is not None:
                try:
                    self.plotter.close()
                except Exception:
                    pass
                self.plotter = None
                self.polydata = None
                self.actor = None
                self._rect_actor = None

        if self.is_ready():
            try:
                self._action_queue.put(close_action)
            except Exception:
                pass

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _execute_on_vis_thread(self, func, timeout=5.0):
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
        if size < 0.1:
            pixel_size = max(1.0, size * 300.0)
        else:
            pixel_size = float(size)

        self.point_size = pixel_size
        if self.is_ready():
            def action():
                if self.actor is not None:
                    self.actor.GetProperty().SetPointSize(float(self.point_size))
                    self.plotter.render()
                    return True
                return False
            try:
                return bool(self._execute_on_vis_thread(action, timeout=1.0))
            except Exception as e:
                print("PyvistaViewer: Error setting point size:", e)
        return False

    def _get_colors(self, points_df, mask):
        mask_indices = mask[:] if hasattr(mask, '__getitem__') else mask
        num_pts = int(np.sum(mask_indices))
        if num_pts == 0:
            return np.zeros((0, 3), dtype=np.float64)

        has_classes = 'class' in points_df.columns
        if has_classes:
            classes = points_df.loc[mask_indices, 'class'].to_numpy(dtype=int)
            if np.any(classes > 0) or not ('r' in points_df.columns and 'g' in points_df.columns and 'b' in points_df.columns):
                return _get_class_colormap(classes)

        if 'r' in points_df.columns and 'g' in points_df.columns and 'b' in points_df.columns:
            rgb = points_df.loc[mask_indices, ['r', 'g', 'b']].to_numpy(dtype=np.float64)
            if rgb.max() > 1.0:
                rgb /= 255.0
            return rgb

        if has_classes:
            classes = points_df.loc[mask_indices, 'class'].to_numpy(dtype=int)
            return _get_class_colormap(classes)

        return np.full((num_pts, 3), 0.7, dtype=np.float64)

    def _get_display_colors_uint8(self):
        """Prepare RGB uint8 colors [0, 255] with yellow highlights for selected indices."""
        if self._current_colors is None:
            return None
        rgb_uint8 = (np.clip(self._current_colors, 0.0, 1.0) * 255).astype(np.uint8)
        if self._picked_indices:
            rgb_uint8[self._picked_indices] = [255, 255, 0]  # Vivid yellow highlight
        return rgb_uint8

    def _apply_colors_to_polydata(self):
        """In-place VTK scalars update without reallocating points."""
        if self.polydata is None or 'colors' not in self.polydata.point_data:
            return
        colors = self._get_display_colors_uint8()
        if colors is None or len(colors) != self.polydata.n_points:
            return
        self.polydata['colors'][:] = colors
        self.polydata.GetPointData().GetScalars().Modified()
        self.plotter.render()

    def update_attributes(self, points_df, mask) -> bool:
        if not self.is_ready() or points_df is None or mask is None:
            return False

        new_colors = self._get_colors(points_df, mask).astype(np.float32)

        def action():
            if self.polydata is not None and self._current_xyz is not None and len(new_colors) == len(self._current_xyz):
                self._current_colors = new_colors
                self._apply_colors_to_polydata()
                return True
            return False

        try:
            return bool(self._execute_on_vis_thread(action, timeout=3.0))
        except Exception as e:
            print("PyvistaViewer: Error updating attributes:", e)
            return False

    def render(self, points_df, mask, preserve_camera: bool = True) -> bool:
        if points_df is None or mask is None:
            return False

        mask_indices = mask[:] if hasattr(mask, '__getitem__') else mask
        num_points = int(np.sum(mask_indices))
        if num_points == 0:
            return False

        xyz = points_df.loc[mask_indices, ['x', 'y', 'z']].to_numpy(dtype=np.float32)
        rgb = self._get_colors(points_df, mask).astype(np.float32)

        if not self.is_ready():
            initial_cam = self.get_camera_parameters() if preserve_camera else None
            self._start_visualizer(xyz, rgb, initial_camera_params=initial_cam)
            return True

        def action():
            saved_cam = self._capture_camera_state() if preserve_camera else None

            self._current_xyz = xyz
            self._current_colors = rgb
            self._picked_indices = []

            # Create new PolyData mesh
            cloud = pv.PolyData(xyz)
            cloud['colors'] = self._get_display_colors_uint8()
            self.polydata = cloud

            if self.actor is not None:
                self.plotter.remove_actor(self.actor)

            self.actor = self.plotter.add_points(
                cloud,
                scalars='colors',
                rgb=True,
                point_size=float(self.point_size),
                render_points_as_spheres=False,
                name='cloud'
            )

            if preserve_camera and saved_cam is not None:
                self._restore_camera_state(saved_cam)
            else:
                self.plotter.reset_camera()

            self.plotter.render()
            return True

        try:
            return bool(self._execute_on_vis_thread(action, timeout=5.0))
        except Exception as e:
            print("PyvistaViewer: Error rendering geometry:", e)
            return False

    def _start_visualizer(self, initial_xyz, initial_rgb, initial_camera_params=None):
        ready_event = threading.Event()

        def _run_loop():
            try:
                plotter = pv.Plotter(title="CloudAnnotation", window_size=(1280, 800))
                plotter.set_background((0.1, 0.1, 0.1))

                # Camera style: Terrain style fixes +Z as up vector (smooth azim/elev orbital navigation)
                plotter.enable_terrain_style(mouse_wheel_zooms=True, shift_pans=True)

                self._current_xyz = initial_xyz
                self._current_colors = initial_rgb
                self._picked_indices = []

                # Build PolyData
                cloud = pv.PolyData(initial_xyz)
                cloud['colors'] = self._get_display_colors_uint8()
                self.polydata = cloud

                actor = plotter.add_points(
                    cloud,
                    scalars='colors',
                    rgb=True,
                    point_size=float(self.point_size),
                    render_points_as_spheres=False,
                    name='cloud'
                )
                self.actor = actor

                # Create 2D rectangle overlay for selection
                rect_source = vtk.vtkPolyData()
                rect_pts = vtk.vtkPoints()
                rect_lines = vtk.vtkCellArray()
                for _ in range(5):
                    rect_pts.InsertNextPoint(0, 0, 0)
                poly_line = vtk.vtkPolyLine()
                poly_line.GetPointIds().SetNumberOfIds(5)
                for i in range(5):
                    poly_line.GetPointIds().SetId(i, i)
                rect_lines.InsertNextCell(poly_line)
                rect_source.SetPoints(rect_pts)
                rect_source.SetLines(rect_lines)

                rect_mapper = vtk.vtkPolyDataMapper2D()
                rect_mapper.SetInputData(rect_source)
                rect_actor = vtk.vtkActor2D()
                rect_actor.SetMapper(rect_mapper)
                rect_actor.GetProperty().SetColor(1.0, 1.0, 0.0)
                rect_actor.GetProperty().SetLineWidth(1.5)
                rect_actor.SetVisibility(False)

                plotter.renderer.AddActor(rect_actor)
                self._rect_actor = rect_actor
                self._rect_pts = rect_pts

                # Apply initial camera
                cam_to_apply = initial_camera_params or self._saved_cam_state
                if cam_to_apply is not None:
                    try:
                        self._restore_camera_state(cam_to_apply, target_plotter=plotter)
                    except Exception:
                        plotter.reset_camera()
                else:
                    plotter.reset_camera()

                plotter.show(auto_close=False, interactive_update=True)

                # Connect mouse events via VTK Interactor observers for Ctrl + Drag selection
                iren = plotter.iren.interactor
                terrain_style = plotter.iren.interactor.GetInteractorStyle()
                none_style = vtk.vtkInteractorStyle()

                def _update_rect_display(p0, p1):
                    x0, y0 = p0
                    x1, y1 = p1
                    self._rect_pts.SetPoint(0, x0, y0, 0)
                    self._rect_pts.SetPoint(1, x1, y0, 0)
                    self._rect_pts.SetPoint(2, x1, y1, 0)
                    self._rect_pts.SetPoint(3, x0, y1, 0)
                    self._rect_pts.SetPoint(4, x0, y0, 0)
                    self._rect_pts.Modified()

                def on_left_down(obj, event):
                    # If Ctrl is pressed, enter box selection mode
                    if obj.GetControlKey():
                        self._is_selecting = True
                        pos = obj.GetEventPosition()
                        self._select_start = pos
                        _update_rect_display(pos, pos)
                        self._rect_actor.SetVisibility(True)
                        # Switch to none_style so VTK camera does not rotate while selecting
                        iren.SetInteractorStyle(none_style)
                        plotter.render()
                    elif not obj.GetShiftKey():
                        # Simple Left Click without Ctrl and without Shift clears selection (just like PPTK)
                        self._select_start = obj.GetEventPosition()

                def on_mouse_move(obj, event):
                    if self._is_selecting and self._select_start is not None:
                        pos = obj.GetEventPosition()
                        _update_rect_display(self._select_start, pos)
                        plotter.render()

                def on_left_up(obj, event):
                    p1 = obj.GetEventPosition()
                    p0 = self._select_start
                    self._select_start = None

                    if self._is_selecting:
                        self._is_selecting = False
                        self._rect_actor.SetVisibility(False)
                        # Restore normal terrain camera interaction style
                        iren.SetInteractorStyle(terrain_style)

                        if p0 is not None:
                            x_min, x_max = min(p0[0], p1[0]), max(p0[0], p1[0])
                            y_min, y_max = min(p0[1], p1[1]), max(p0[1], p1[1])

                            # If dragging a rectangle, accumulate selection (union) like PPTK
                            if abs(x_max - x_min) >= 3 or abs(y_max - y_min) >= 3:
                                new_indices = self._perform_box_selection(x_min, x_max, y_min, y_max, plotter.renderer)
                                if new_indices:
                                    # Cumulative selection: merge uniquely
                                    curr_set = set(self._picked_indices)
                                    curr_set.update(new_indices)
                                    self._picked_indices = list(curr_set)

                        self._apply_colors_to_polydata()
                    elif p0 is not None and not obj.GetControlKey() and not obj.GetShiftKey():
                        # Single click without drag: clear selection
                        x_diff = abs(p1[0] - p0[0])
                        y_diff = abs(p1[1] - p0[1])
                        if x_diff < 3 and y_diff < 3 and self._picked_indices:
                            self._picked_indices = []
                            self._apply_colors_to_polydata()

                def on_key_press(obj, event):
                    key = obj.GetKeySym()
                    if key in ['c', 'C']:
                        self._picked_indices = []
                        self._apply_colors_to_polydata()

                iren.AddObserver('LeftButtonPressEvent', on_left_down, 10.0)
                iren.AddObserver('MouseMoveEvent', on_mouse_move, 10.0)
                iren.AddObserver('LeftButtonReleaseEvent', on_left_up, 10.0)
                iren.AddObserver('KeyPressEvent', on_key_press, 10.0)

                with self._lock:
                    self.plotter = plotter
                    self._is_running = True

                ready_event.set()

                # Event loop
                while self._is_running:
                    while not self._action_queue.empty():
                        try:
                            action = self._action_queue.get_nowait()
                            action()
                            self._action_queue.task_done()
                        except queue.Empty:
                            break
                        except Exception as qe:
                            print("PyvistaViewer: Action error:", qe)

                    with self._lock:
                        if self.plotter is None:
                            break
                        self.plotter.update()

                    time.sleep(0.016)

            except Exception as e:
                import traceback
                print("PyvistaViewer: Loop error:", e)
                traceback.print_exc()
            finally:
                self._is_running = False
                ready_event.set()

        self._thread = threading.Thread(target=_run_loop, daemon=True)
        self._thread.start()
        if not ready_event.wait(timeout=5.0):
            print("PyvistaViewer: Timeout waiting for window initialization.")

    def _perform_box_selection(self, x_min, x_max, y_min, y_max, renderer):
        """Vectorized screen-space bounding box filter on 3D point cloud using VTK camera projection."""
        if self._current_xyz is None or len(self._current_xyz) == 0:
            return []

        try:
            cam = renderer.GetActiveCamera()
            composite_proj = cam.GetCompositeProjectionTransformMatrix(renderer.GetTiledAspectRatio(), -1, 1)

            mat = np.zeros((4, 4), dtype=np.float32)
            for i in range(4):
                for j in range(4):
                    mat[i, j] = composite_proj.GetElement(i, j)

            N = len(self._current_xyz)
            pts_h = np.hstack([self._current_xyz, np.ones((N, 1), dtype=np.float32)])
            clip = pts_h @ mat.T
            w = clip[:, 3:4]
            valid_depth = w[:, 0] > 1e-4
            ndc = clip[:, :2] / np.where(np.abs(w) > 1e-4, w, 1.0)

            win_w, win_h = renderer.GetSize()
            screen_x = (ndc[:, 0] + 1.0) * 0.5 * win_w
            screen_y = (ndc[:, 1] + 1.0) * 0.5 * win_h

            in_box = valid_depth & (screen_x >= x_min) & (screen_x <= x_max) & (screen_y >= y_min) & (screen_y <= y_max)
            return np.where(in_box)[0].tolist()
        except Exception as e:
            print("PyvistaViewer: Box selection error:", e)
            return []

    def get_selected_indices(self) -> list:
        with self._lock:
            return list(self._picked_indices)

    def set_selected_indices(self, indices: list) -> bool:
        if not self.is_ready():
            return False

        def action():
            self._picked_indices = list(indices) if indices else []
            self._apply_colors_to_polydata()
            return True

        try:
            return bool(self._execute_on_vis_thread(action, timeout=1.0))
        except Exception:
            return False

    def _capture_camera_state(self, target_plotter=None):
        plotter = target_plotter or self.plotter
        if plotter is None:
            return None
        cam = plotter.camera
        return {
            'position': tuple(cam.position),
            'focal_point': tuple(cam.focal_point),
            'up': tuple(cam.up),
            'clipping_range': tuple(cam.clipping_range),
        }

    def _restore_camera_state(self, state, target_plotter=None):
        plotter = target_plotter or self.plotter
        if plotter is None or state is None:
            return
        cam = plotter.camera
        if 'position' in state:
            cam.position = state['position']
        if 'focal_point' in state:
            cam.focal_point = state['focal_point']
        if 'up' in state:
            cam.up = state['up']
        if 'clipping_range' in state:
            cam.clipping_range = state['clipping_range']

    def get_camera_parameters(self):
        if not self.is_ready():
            return self._saved_cam_state
        return self._capture_camera_state()

    def set_camera_parameters(self, params) -> bool:
        if params is None:
            return False
        self._saved_cam_state = params
        if not self.is_ready():
            return True

        def action():
            self._restore_camera_state(params)
            self.plotter.render()
            return True

        try:
            return bool(self._execute_on_vis_thread(action, timeout=1.0))
        except Exception:
            return False
