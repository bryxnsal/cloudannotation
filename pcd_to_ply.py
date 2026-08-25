import open3d as o3d

# Cargar archivo PCD
pcd = o3d.io.read_point_cloud("/home/zahir/cloudannotation-master/dataset/GlobalMap.pcd")

# Guardar como PLY
o3d.io.write_point_cloud("/home/zahir/cloudannotation-master/dataset/GlobalMap.ply", pcd)

print("Conversión completada.")