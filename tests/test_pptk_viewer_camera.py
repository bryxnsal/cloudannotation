import sys
import types
import unittest


# The production adapter imports PPTK at module import time.  Use a small
# placeholder so this unit test remains runnable where the native viewer is
# unavailable.
sys.modules.setdefault('pptk', types.SimpleNamespace())

from core.viewer.pptk_viewer import PptkViewerAdapter


class FakeCameraController:
    def __init__(self, perspective):
        self.perspective = perspective
        self.restore_attempts = 0

    def get_perspective(self):
        return self.perspective

    def set_perspective(self, perspective):
        self.restore_attempts += 1
        self.perspective = perspective
        return True


class FakeViewer:
    def __init__(self):
        self.play_calls = []

    def play(self, *args, **kwargs):
        self.play_calls.append((args, kwargs))


class TestPptkViewerCameraRestore(unittest.TestCase):
    def test_commits_camera_pose_for_the_next_mouse_drag(self):
        expected = [10.0, 20.0, 30.0, 0.4, -0.2, 50.0]
        controller = FakeCameraController(expected)
        adapter = PptkViewerAdapter(controller)
        adapter.viewer = FakeViewer()

        self.assertTrue(adapter.restore_camera_after_geometry_load(expected))
        self.assertEqual(controller.restore_attempts, 1)
        self.assertEqual(
            adapter.viewer.play_calls,
            [(([expected],), {
                'ts': [0.0],
                'tlim': [0.0, 0.0],
                'repeat': False,
                'interp': 'constant',
            })],
        )
