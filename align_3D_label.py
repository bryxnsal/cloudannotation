import open3d as o3d
import numpy as np
from plyfile import PlyData, PlyElement

# -----------------------------
# 1️⃣ Cargar PLY y separar etiquetas
# -----------------------------
filename = "/home/zahir/cloudannotation-master/dataset/GlobalMap/GlobalMap.ply"
plydata = PlyData.read(filename)
vertex = plydata['vertex'].data

# Detectar el campo de etiquetas
if 'class' in vertex.dtype.names:
    label_field = 'class'
elif 'scalar_Label' in vertex.dtype.names:
    label_field = 'scalar_Label'
else:
    raise ValueError("El PLY no contiene campo 'class' ni 'scalar_Label'")

# Extraer puntos y etiquetas
points = np.vstack([vertex['x'], vertex['y'], vertex['z']]).T
labels = vertex[label_field]

# -----------------------------
# 2️⃣ Convertir a Open3D y filtrar outliers
# -----------------------------
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(points)

pcd, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
labels = labels[ind]  # Filtrar etiquetas correspondientes

# -----------------------------
# 3️⃣ Detectar plano y refinar con PCA
# -----------------------------
plane_model, inliers = pcd.segment_plane(distance_threshold=0.01,
                                         ransac_n=3,
                                         num_iterations=2000)
plane_points = np.asarray(pcd.points)[inliers]

center = plane_points.mean(axis=0)
points_centered = plane_points - center
cov = np.cov(points_centered.T)
eigvals, eigvecs = np.linalg.eigh(cov)
normal_refined = eigvecs[:, np.argmin(eigvals)]
normal_refined /= np.linalg.norm(normal_refined)

# Asegurar que la normal apunte hacia arriba
if normal_refined[2] < 0:
    normal_refined = -normal_refined

# -----------------------------
# 4️⃣ Rotar para alinear con Z
# -----------------------------
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

pcd.rotate(R, center=pcd.get_center())

# -----------------------------
# 5️⃣ Centrar en Z=0
# -----------------------------
points_rot = np.asarray(pcd.points)
min_z = points_rot[:, 2].min()
pcd.translate((0, 0, -min_z))

# -----------------------------
# 6️⃣ Guardar PLY con etiquetas
# -----------------------------
points_aligned = np.asarray(pcd.points)
vertex_all = np.zeros(points_aligned.shape[0],
                      dtype=[('x', 'f4'), ('y', 'f4'), ('z', 'f4'), (label_field, 'i4')])
vertex_all['x'] = points_aligned[:, 0]
vertex_all['y'] = points_aligned[:, 1]
vertex_all['z'] = points_aligned[:, 2]
vertex_all[label_field] = labels

ply_out = PlyData([PlyElement.describe(vertex_all, 'vertex')], text=True)
ply_out.write("GlobalMap_aligned_with_labels.ply")

print("✅ Nube de puntos alineada y guardada con etiquetas.")