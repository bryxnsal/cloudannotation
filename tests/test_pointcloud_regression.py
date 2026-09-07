"""
Regression test harness for PointCloud.
Ensures current behaviors remain intact through modular refactoring phases:
1. Instantiation & attributes
2. Data structure & point count
3. Selection & Mask logic
4. Undo / Redo engine
5. Point size dynamic setting
6. Stats generation
7. Save / Reload roundtrip
"""
import os
import sys
import unittest
import numpy as np
import pandas as pd

from PointCloud import PointCloud
from Mask import Mask
from plyfile import PlyData, PlyElement

class TestPointCloudRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_ply = "test_regression_cloud.ply"
        num_points = 500
        xyz = np.random.uniform(0.0, 50.0, (num_points, 3)).astype(np.float32)
        classes = np.random.choice([0, 1, 2, 3], size=num_points).astype(np.int32)
        
        vertex_data = np.empty(num_points, dtype=[
            ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
            ('class', 'i4')
        ])
        vertex_data['x'] = xyz[:, 0]
        vertex_data['y'] = xyz[:, 1]
        vertex_data['z'] = xyz[:, 2]
        vertex_data['class'] = classes

        el = PlyElement.describe(vertex_data, 'vertex')
        PlyData([el], text=False).write(cls.test_ply)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_ply):
            os.remove(cls.test_ply)
        for temp_file in ["test_advance.ply", "test_exported.ply", "advances/test_exported.ply"]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        if os.path.exists("advances") and not os.listdir("advances"):
            os.rmdir("advances")


    def setUp(self):
        self.pc = PointCloud(self.test_ply, point_size=0.01, render=False, labels=14)

    def test_01_cloud_loading_and_shape(self):
        """Verify cloud loads correctly with proper DataFrame shape and attributes."""
        self.assertEqual(len(self.pc), 500)
        self.assertIn('x', self.pc.points.columns)
        self.assertIn('y', self.pc.points.columns)
        self.assertIn('z', self.pc.points.columns)
        self.assertIn('class', self.pc.points.columns)
        self.assertEqual(self.pc.point_size, 0.01)
        self.assertIsNotNone(self.pc.base_classes)
        self.assertEqual(len(self.pc.base_classes), 500)

    def test_02_selection_and_masks(self):
        """Verify selection logic by class and indices."""
        mask = self.pc.select(classes=[1], highlighted=False)
        expected_count = np.sum(self.pc.points['class'] == 1)
        self.assertEqual(np.sum(mask.bools), expected_count)

        self.assertFalse(self.pc.is_work_area_active())
        self.pc.set_work_area(mask)
        self.assertTrue(self.pc.is_work_area_active())
        self.assertEqual(np.sum(self.pc.active_roi.bools), expected_count)
        self.pc.clear_work_area()
        self.assertFalse(self.pc.is_work_area_active())

    def test_03_classification_and_undo_redo(self):
        """Verify classify modifies points and undo/redo stacks operate correctly."""
        target_indices = np.array([0, 1, 2, 3, 4])
        orig_classes = self.pc.points.loc[target_indices, 'class'].to_numpy(copy=True)
        
        mask = Mask(len(self.pc), False)
        mask.bools[target_indices] = True

        self.pc.classify(9, overwrite=True, mask=mask, preserve_camera=False)
        self.assertTrue(np.all(self.pc.points.loc[target_indices, 'class'] == 9))
        self.assertEqual(len(self.pc.undo_stack), 1)
        self.assertEqual(len(self.pc.redo_stack), 0)

        undo_res = self.pc.undo()
        self.assertTrue(undo_res)
        np.testing.assert_array_equal(self.pc.points.loc[target_indices, 'class'].to_numpy(), orig_classes)
        self.assertEqual(len(self.pc.undo_stack), 0)
        self.assertEqual(len(self.pc.redo_stack), 1)

        redo_res = self.pc.redo()
        self.assertTrue(redo_res)
        self.assertTrue(np.all(self.pc.points.loc[target_indices, 'class'] == 9))
        self.assertEqual(len(self.pc.undo_stack), 1)
        self.assertEqual(len(self.pc.redo_stack), 0)

    def test_04_point_size_setter(self):
        """Verify dynamic point size setter."""
        self.pc.set_point_size(0.025)
        self.assertEqual(self.pc.point_size, 0.025)

    def test_05_stats_generation(self):
        """Verify get_stats outputs accurate metadata."""
        stats = self.pc.get_stats()
        self.assertEqual(stats['total_points'], 500)
        self.assertEqual(stats['point_size'], self.pc.point_size)
        self.assertIn('classes_count', stats)
        self.assertIn('file_size_mb', stats)

    def test_06_save_and_reload(self):
        """Verify write and reload_from_file roundtrip."""
        export_file = "test_exported.ply"
        self.pc.write(export_file, overwrite=True)
        expected_path = os.path.join("advances", export_file)
        self.assertTrue(os.path.exists(expected_path))

        # Reload into cloud
        res = self.pc.reload_from_file(expected_path, preserve_camera=False)
        self.assertTrue(res)
        self.assertEqual(len(self.pc), 500)


if __name__ == '__main__':
    unittest.main()

