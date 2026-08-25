import os
import numpy as np
import open3d as o3d
from plyfile import PlyData, PlyElement
import json

def read_pcd(pcd_path):
    """Read PCD using Open3D and return XYZ and RGB arrays."""
    pcd = o3d.io.read_point_cloud(pcd_path)
    xyz = np.asarray(pcd.points)
    rgb = np.asarray(pcd.colors) if pcd.has_colors() else None
    return xyz, rgb

def write_ply_xyz(ply_path, xyz, rgb=None):
    """Write XYZ (+ RGB) to PLY file."""
    if rgb is not None:
        vertex = np.array(
            [tuple(xyz[i]) + tuple((rgb[i]*255).astype(np.uint8)) for i in range(len(xyz))],
            dtype=[('x','f4'),('y','f4'),('z','f4'),
                   ('red','u1'),('green','u1'),('blue','u1')]
        )
    else:
        vertex = np.array([tuple(xyz[i]) for i in range(len(xyz))],
                          dtype=[('x','f4'),('y','f4'),('z','f4')])
    PlyData([PlyElement.describe(vertex,'vertex')], text=False).write(ply_path)

def align_to_z_robust(xyz, ground_threshold=0.5, use_ransac=True, grid_size=2.0):
    """
    Robust alignment for curved/uneven ground:
    1. Uses RANSAC or grid-based approach to find dominant ground orientation
    2. Aligns average ground normal to Z+
    3. Removes pitch/roll rotations
    """
    z_min = np.percentile(xyz[:,2], 5)
    ground_points = xyz[xyz[:,2] < z_min + ground_threshold]
    
    if use_ransac:
        # Method 1: RANSAC to find best plane through noisy ground
        best_normal = None
        best_inliers = 0
        n_iterations = 1000
        inlier_threshold = 0.05
        
        for _ in range(n_iterations):
            # Sample 3 random points
            if len(ground_points) < 3:
                break
            sample_idx = np.random.choice(len(ground_points), 3, replace=False)
            sample_points = ground_points[sample_idx]
            
            # Compute plane normal
            v1 = sample_points[1] - sample_points[0]
            v2 = sample_points[2] - sample_points[0]
            normal = np.cross(v1, v2)
            if np.linalg.norm(normal) < 1e-6:
                continue
            normal = normal / np.linalg.norm(normal)
            
            # Ensure upward pointing
            if normal[2] < 0:
                normal = -normal
            
            # Count inliers
            distances = np.abs(np.dot(ground_points - sample_points[0], normal))
            inliers = np.sum(distances < inlier_threshold)
            
            if inliers > best_inliers:
                best_inliers = inliers
                best_normal = normal
        
        if best_normal is None:
            # Fallback to simple covariance
            cov = np.cov(ground_points.T)
            eigvals, eigvecs = np.linalg.eigh(cov)
            best_normal = eigvecs[:, np.argmin(eigvals)]
            if best_normal[2] < 0:
                best_normal = -best_normal
        
        normal = best_normal
        
    else:
        # Method 2: Grid-based local normals averaging
        x_range = np.ptp(ground_points[:, 0])
        y_range = np.ptp(ground_points[:, 1])
        n_x = max(3, int(x_range / grid_size))
        n_y = max(3, int(y_range / grid_size))
        
        x_min, x_max = ground_points[:, 0].min(), ground_points[:, 0].max()
        y_min, y_max = ground_points[:, 1].min(), ground_points[:, 1].max()
        
        local_normals = []
        
        for i in range(n_x):
            for j in range(n_y):
                x_start = x_min + i * x_range / n_x
                x_end = x_min + (i + 1) * x_range / n_x
                y_start = y_min + j * y_range / n_y
                y_end = y_min + (j + 1) * y_range / n_y
                
                # Get points in this grid cell
                mask = ((ground_points[:, 0] >= x_start) & (ground_points[:, 0] < x_end) &
                        (ground_points[:, 1] >= y_start) & (ground_points[:, 1] < y_end))
                cell_points = ground_points[mask]
                
                if len(cell_points) >= 5:  # Need minimum points for reliable normal
                    cov = np.cov(cell_points.T)
                    eigvals, eigvecs = np.linalg.eigh(cov)
                    local_normal = eigvecs[:, np.argmin(eigvals)]
                    if local_normal[2] < 0:
                        local_normal = -local_normal
                    local_normals.append(local_normal)
        
        if local_normals:
            # Average all local normals
            normal = np.mean(local_normals, axis=0)
            normal = normal / np.linalg.norm(normal)
        else:
            # Fallback
            cov = np.cov(ground_points.T)
            eigvals, eigvecs = np.linalg.eigh(cov)
            normal = eigvecs[:, np.argmin(eigvals)]
            if normal[2] < 0:
                normal = -normal

    # Step 1: Rotate to align normal with Z+
    target = np.array([0,0,1])
    v = np.cross(normal, target)
    s = np.linalg.norm(v)
    c = np.dot(normal, target)
    
    if s < 1e-6:  # Already aligned
        R1 = np.eye(3)
    else:
        vx = np.array([[0,-v[2],v[1]],
                       [v[2],0,-v[0]],
                       [-v[1],v[0],0]])
        R1 = np.eye(3) + vx + vx @ vx * ((1-c)/(s**2))
    
    xyz_z_aligned = xyz @ R1.T
    
    # Step 2: Remove pitch/roll using aligned ground points
    ground_points_aligned = ground_points @ R1.T
    xy_ground = ground_points_aligned[:, :2]  # Only X,Y coordinates
    
    # For curved ground, use the longest span direction
    xy_range = np.ptp(xy_ground, axis=0)  # Range in X and Y
    if xy_range[0] > xy_range[1]:
        # Ground extends more in X, align longest direction with X-axis
        cov_xy = np.cov(xy_ground.T)
        eigvals_xy, eigvecs_xy = np.linalg.eigh(cov_xy)
        principal_dir = eigvecs_xy[:, np.argmax(eigvals_xy)]
    else:
        # Ground extends more in Y, align longest direction with Y-axis
        cov_xy = np.cov(xy_ground.T)
        eigvals_xy, eigvecs_xy = np.linalg.eigh(cov_xy)
        principal_dir = eigvecs_xy[:, np.argmax(eigvals_xy)]
    
    # Align principal direction with X-axis
    angle = np.arctan2(principal_dir[1], principal_dir[0])
    
    # Create rotation matrix around Z-axis
    cos_a, sin_a = np.cos(-angle), np.sin(-angle)
    R2 = np.array([[cos_a, -sin_a, 0],
                   [sin_a,  cos_a, 0],
                   [0,      0,     1]])
    
    # Apply both rotations
    xyz_final = xyz_z_aligned @ R2.T
    R_total = R2 @ R1
    
    return xyz_final, R_total

def align_to_z_canonical(xyz, ground_threshold=0.5):
    """
    Original method (kept for compatibility)
    """
    return align_to_z_robust(xyz, ground_threshold, use_ransac=False)

def align_to_z_simple(xyz, ground_threshold=0.1):
    """
    Simple version: Just ensure Z+ alignment without constraining horizontal orientation
    """
    z_min = np.percentile(xyz[:,2], 5)
    ground_points = xyz[xyz[:,2] < z_min + ground_threshold]
    cov = np.cov(ground_points.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    normal = eigvecs[:, np.argmin(eigvals)]

    if normal[2] < 0:
        normal = -normal

    target = np.array([0,0,1])
    v = np.cross(normal, target)
    s = np.linalg.norm(v)
    c = np.dot(normal, target)
    
    if s < 1e-6:
        return xyz, np.eye(3)
    
    vx = np.array([[0,-v[2],v[1]],
                   [v[2],0,-v[0]],
                   [-v[1],v[0],0]])
    R = np.eye(3) + vx + vx @ vx * ((1-c)/(s**2))
    return xyz @ R.T, R

def process_globalmap_pcd(dataset_folder, method='robust_ransac'):
    """
    Process point clouds with different alignment methods:
    - 'simple': Original simple Z-alignment (may have pitch/roll)
    - 'canonical': Original canonical alignment (assumes planar ground)  
    - 'robust_ransac': RANSAC-based alignment for curved ground
    - 'robust_grid': Grid-based alignment for curved ground
    """
    for folder_name in os.listdir(dataset_folder):
        map_folder = os.path.join(dataset_folder, folder_name, "map")
        pcd_path = os.path.join(map_folder, "GlobalMap.pcd")
        if os.path.exists(pcd_path):
            print(f"Processing: {pcd_path}")
            xyz, rgb = read_pcd(pcd_path)
            
            if method == 'simple':
                xyz_rot, R = align_to_z_simple(xyz)
                print(f"Applied simple Z-alignment (pitch/roll may remain)")
            elif method == 'canonical':
                xyz_rot, R = align_to_z_canonical(xyz)
                print(f"Applied canonical alignment (assumes planar ground)")
            elif method == 'robust_ransac':
                xyz_rot, R = align_to_z_robust(xyz, use_ransac=True)
                print(f"Applied RANSAC-based alignment for curved ground")
            elif method == 'robust_grid':
                xyz_rot, R = align_to_z_robust(xyz, use_ransac=False)
                print(f"Applied grid-based alignment for curved ground")
            
            out_ply = os.path.join(map_folder, "GlobalMap.ply")
            write_ply_xyz(out_ply, xyz_rot, rgb)
            print(f"Aligned PLY saved: {out_ply}")

if __name__ == "__main__":
    dataset_folder = "dataset"
    
    # Choose method based on your ground type:
    # 'robust_ransac' - Best for curved/uneven ground with outliers
    # 'robust_grid' - Good for gently curved ground  
    # 'canonical' - Good for mostly planar ground
    # 'simple' - Basic Z-alignment only
    
    process_globalmap_pcd(dataset_folder, method='robust_ransac')