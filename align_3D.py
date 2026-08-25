import open3d as o3d
import numpy as np

# Load point cloud
pcd = o3d.io.read_point_cloud("/home/zahir/cloudannotation-master/dataset/GlobalMap/GlobalMap.ply")

# Statistical outlier removal
pcd, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

# Detect plane with RANSAC
plane_model, inliers = pcd.segment_plane(distance_threshold=0.01,
                                         ransac_n=3,
                                         num_iterations=2000)
[a, b, c, d] = plane_model

# Select only the plane inliers
plane_points = np.asarray(pcd.points)[inliers]

# Refinement with PCA
center = plane_points.mean(axis=0)
points_centered = plane_points - center
cov = np.cov(points_centered.T)
eigvals, eigvecs = np.linalg.eigh(cov)
normal_refined = eigvecs[:, np.argmin(eigvals)]
normal_refined /= np.linalg.norm(normal_refined)

# Rotate to align normal with Z axis
target = np.array([0, 0, 1])
v = np.cross(normal_refined, target)
s = np.linalg.norm(v)
c = np.dot(normal_refined, target)
if s < 1e-6:
    R = np.eye(3)
else:
    vx = np.array([[0, -v[2], v[1]],
                   [v[2], 0, -v[0]],
                   [-v[1], v[0], 0]])
    R = np.eye(3) + vx + vx @ vx * ((1 - c) / (s**2))

# Apply rotation to the entire cloud
pcd.rotate(R, center=pcd.get_center())

# Center plane at z=0
points_rot = np.asarray(pcd.points)
min_z = points_rot[:, 2].min()
pcd.translate((0, 0, -min_z))

# Save result
o3d.io.write_point_cloud("GlobalMap_aligned.ply", pcd)
print("Point cloud aligned and saved as 'GlobalMap_aligned.ply'")