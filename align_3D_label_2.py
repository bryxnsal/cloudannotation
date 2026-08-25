import open3d as o3d
import numpy as np
from plyfile import PlyData, PlyElement

# -----------------------------
# 1️⃣ Cargar PLY y etiquetas
# -----------------------------
filename = "/home/zahir/cloudannotation-master/dataset/GlobalMap/GlobalMap.ply"
plydata = PlyData.read(filename)
vertex = plydata['vertex'].data

if 'class' in vertex.dtype.names:
    label_field = 'class'
elif 'scalar_Label' in vertex.dtype.names:
    label_field = 'scalar_Label'
else:
    raise ValueError("El PLY no contiene campo 'class' ni 'scalar_Label'")

points = np.vstack([vertex['x'], vertex['y'], vertex['z']]).T
labels = vertex[label_field]

# -----------------------------
# 2️⃣ Open3D + filtro de outliers
# -----------------------------
pcd = o3d.geometry.PointCloud()
pcd.points = o3d.utility.Vector3dVector(points)

pcd, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
labels = labels[ind]

# -----------------------------
# 3️⃣ Detectar plano + PCA
# -----------------------------
plane_model, inliers = pcd.segment_plane(
    distance_threshold=0.01,
    ransac_n=3,
    num_iterations=2000
)

plane_points = np.asarray(pcd.points)[inliers]

center = plane_points.mean(axis=0)
points_centered = plane_points - center
cov = np.cov(points_centered.T)

eigvals, eigvecs = np.linalg.eigh(cov)

# -----------------------------
# 4️⃣ Definir ejes
# -----------------------------

# Y → normal del plano (menor autovalor)
y_axis = eigvecs[:, np.argmin(eigvals)]
y_axis /= np.linalg.norm(y_axis)

# Asegurar Y hacia arriba
if y_axis[1] > 0:
    y_axis = -y_axis

# X → dirección dominante del plano (mayor varianza)
x_axis = eigvecs[:, np.argmax(eigvals)]
x_axis -= x_axis.dot(y_axis) * y_axis  # ortogonalizar
x_axis /= np.linalg.norm(x_axis)

# Z → eje estable (mano derecha)
# X × Y = Z
z_axis = np.cross(x_axis, y_axis)
z_axis /= np.linalg.norm(z_axis)

# -----------------------------
# 5️⃣ Rotación determinista
# -----------------------------
R = np.vstack([x_axis, y_axis, z_axis]).T
pcd.rotate(R, center=center)

# -----------------------------
# 6️⃣ Trasladar para que Y mínimo sea 0
# -----------------------------
points_rot = np.asarray(pcd.points)
pcd.translate((0, -points_rot[:, 1].min(), 0))

# -----------------------------
# 7️⃣ Guardar PLY con etiquetas
# -----------------------------
points_aligned = np.asarray(pcd.points)

vertex_all = np.zeros(
    points_aligned.shape[0],
    dtype=[('x', 'f4'), ('y', 'f4'), ('z', 'f4'), (label_field, 'i4')]
)

vertex_all['x'] = points_aligned[:, 0]
vertex_all['y'] = points_aligned[:, 1]
vertex_all['z'] = points_aligned[:, 2]
vertex_all[label_field] = labels

ply_out = PlyData([PlyElement.describe(vertex_all, 'vertex')], text=True)
ply_out.write("GlobalMap_aligned_with_labels.ply")

print("✅ Nube alineada: Y arriba, X dominante, Z estable.")