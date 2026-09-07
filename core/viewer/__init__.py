"""
Viewer module for 3D point cloud visualization and camera navigation.
"""
from core.viewer.base_viewer import BaseViewerAdapter
from core.viewer.camera_controller import CameraController

def get_open3d_viewer_adapter():
    from core.viewer.open3d_viewer import Open3dViewerAdapter
    return Open3dViewerAdapter

def get_pptk_viewer_adapter():
    from core.viewer.pptk_viewer import PptkViewerAdapter
    return PptkViewerAdapter

def __getattr__(name):
    if name == 'PptkViewerAdapter':
        return get_pptk_viewer_adapter()
    raise AttributeError(name)

__all__ = [
    'BaseViewerAdapter',
    'CameraController',
    'PptkViewerAdapter',
    'get_open3d_viewer_adapter',
    'get_pptk_viewer_adapter',
]
