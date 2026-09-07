"""
CameraController: Manages 3D camera viewpoints, projections, and smooth perspective transitions.
"""
import numpy as np

class CameraController:
    """
    Handles camera perspective capture, restoration, viewpoint preservation,
    and adaptive focus anchoring when switching between full view and isolated ROIs.
    """
    def __init__(self, viewer_accessor):
        """
        :param viewer_accessor: Callable returning the active pptk viewer or None.
        """
        self._get_viewer = viewer_accessor
        self.saved_cameras = {}

    def get_perspective(self):
        """
        Capture current perspective parameters from viewer:
        [lookat_x, lookat_y, lookat_z, phi, theta, r]
        """
        viewer = self._get_viewer()
        if viewer is None:
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        try:
            lookat = viewer.get('lookat')
            phi = viewer.get('phi')
            theta = viewer.get('theta')
            r = viewer.get('r')
            return [
                float(lookat[0]), float(lookat[1]), float(lookat[2]),
                float(phi), float(theta), float(r)
            ]
        except Exception:
            return [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def set_perspective(self, p):
        """
        Apply perspective parameters to active viewer.
        :param p: list or array of at least 6 floats [lookat_x, lookat_y, lookat_z, phi, theta, r]
        """
        viewer = self._get_viewer()
        if viewer is None or p is None or len(p) < 6:
            return False
        try:
            viewer.set(lookat=p[0:3], phi=float(p[3]), theta=float(p[4]), r=float(p[5]))
            return True
        except Exception as e:
            print("Error setting camera perspective:", e)
            return False

    def save_camera(self, name='default'):
        """Store current camera viewpoint under a given name."""
        persp = self.get_perspective()
        self.saved_cameras[name] = persp
        return persp

    def restore_camera(self, name='default'):
        """Restore previously saved camera viewpoint."""
        if name in self.saved_cameras:
            return self.set_perspective(self.saved_cameras[name])
        return False

    def compute_anchor_perspective(self, cam_persp, subset_xyz):
        """
        Compute an orbit-friendly camera perspective anchored at the center of a subset of points,
        preserving current viewing angles (phi, theta) and adapting camera distance (r).
        """
        if cam_persp is None or subset_xyz is None or len(subset_xyz) == 0:
            return cam_persp

        try:
            min_bounds = np.min(subset_xyz, axis=0)
            max_bounds = np.max(subset_xyz, axis=0)
            subset_center = (min_bounds + max_bounds) / 2.0
            subset_extent = float(np.linalg.norm(max_bounds - min_bounds))

            old_lookat = np.array(cam_persp[0:3], dtype=float)
            phi = float(cam_persp[3])
            theta = float(cam_persp[4])
            r = float(cam_persp[5])

            view_dir = np.array([
                np.cos(theta) * np.cos(phi),
                np.cos(theta) * np.sin(phi),
                np.sin(theta)
            ])
            eye = old_lookat + r * view_dir

            d = eye - subset_center
            r_new = float(np.linalg.norm(d))

            min_r = max(0.5, subset_extent * 0.8)
            max_r = max(min_r * 4.0, 500.0)
            r_new = max(min_r, min(r_new, max_r))

            phi_new = float(np.arctan2(d[1], d[0]))
            theta_new = float(np.arcsin(np.clip(d[2] / (r_new if r_new > 1e-4 else 1.0), -1.0, 1.0)))

            return [
                float(subset_center[0]),
                float(subset_center[1]),
                float(subset_center[2]),
                phi_new,
                theta_new,
                r_new
            ]
        except Exception as e:
            print("Error computing anchor perspective:", e)
            return cam_persp
