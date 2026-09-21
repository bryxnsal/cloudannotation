"""
BaseViewerAdapter: Abstract base class defining the contract for all 3D point cloud viewers.
"""
from abc import ABC, abstractmethod


class BaseViewerAdapter(ABC):
    """
    Abstract contract for point cloud rendering, interaction, attribute updates and selection.
    """
    def __init__(self, camera_controller=None):
        self.camera_controller = camera_controller
        self.point_size = 0.01

    @property
    def viewer(self):
        """Underlying viewer handle if any (e.g. pptk viewer, pyvista plotter, etc.)."""
        return None

    @abstractmethod
    def is_ready(self) -> bool:
        """Return True if viewer window/process is active and responsive."""
        pass

    @abstractmethod
    def close(self):
        """Close viewer window gracefully and clean up resources."""
        pass

    @abstractmethod
    def set_point_size(self, size: float) -> bool:
        """Update point rendering size dynamically."""
        pass

    @abstractmethod
    def update_attributes(self, points_df, mask) -> bool:
        """Update color and classification attributes on currently loaded geometry."""
        pass

    @abstractmethod
    def render(self, points_df, mask, preserve_camera: bool = True) -> bool:
        """Render point cloud into viewer, optionally preserving camera perspective."""
        pass

    @abstractmethod
    def get_selected_indices(self) -> list:
        """Return indices currently selected by the user in the 3D viewport."""
        pass

    @abstractmethod
    def set_selected_indices(self, indices: list) -> bool:
        """Highlight given relative indices in the viewport."""
        pass

    def get_camera_parameters(self):
        """Retrieve current viewer camera parameters if supported."""
        return None

    def set_camera_parameters(self, params) -> bool:
        """Apply camera parameters if supported."""
        return False
