#!/usr/bin/env python3
import open3d as o3d
import numpy as np
import pandas as pd
from plyfile import PlyData, PlyElement
from sklearn.cluster import DBSCAN

# ========================
# CONFIGURACIÓN
# ========================
LABEL_POSTE = 6
LABEL_CABLE = 7
LABEL_MT_POSTE = 11
LABEL_BT_POSTE = 12
LABEL_MT_CABLE = 13
LABEL_BT_CABLE = 14

ALTURA_UMBRAL = 12.0  # metros
EPS_CLUSTER = 2.0     # eps en DBSCAN para clustering 3D
MIN_SAMPLES = 10      # mínimo puntos para considerar cluster

# ========================
# FUNCIONES AUXILIARES
# ========================
def medir_poste(poste_points):
    """Calcula la altura 3D, centro (X,Y) y radio del poste"""
    punto_bajo = np.min(poste_points, axis=0)
    punto_alto = np.max(poste_points, axis=0)
    altura = np.linalg.norm(punto_alto - punto_bajo)
    cx = np.median(poste_points[:, 0])
    cy = np.median(poste_points[:, 1])
    radio = np.median(np.sqrt((poste_points[:, 0] - cx) ** 2 +
                              (poste_points[:, 1] - cy) ** 2))
    return altura, cx, cy, radio

def asignar_cable(poste_info, cable_points):
    """Asigna tipo de poste más cercano a cada cable"""
    tipos = []
    for p in cable_points[:, :3]:
        dist = np.sqrt((poste_info['cx'].values - p[0])**2 +
                       (poste_info['cy'].values - p[1])**2)
        idx_min = np.argmin(dist)
        tipos.append(poste_info.iloc[idx_min]['tipo'])
    return np.array(tipos)

# ========================
# PIPELINE PRINCIPAL
# ========================
def procesar_nube(input_ply, output_ply, postes_xlsx):
    """Procesa la nube: detecta postes y cables, etiqueta MT/BT, guarda PLY y Excel"""
    
    # --- Leer nube ---
    pcd = o3d.io.read_point_cloud(input_ply)
    np_points = np.asarray(pcd.points)
    
    plydata = PlyData.read(input_ply)
    vertex = plydata['vertex'].data
    if 'class' in vertex.dtype.names:
        labels = np.array(vertex['class'], dtype=np.int32)
        label_field = 'class'
    else:
        raise ValueError("El PLY no tiene campo 'class''")
    
    df = pd.DataFrame(np_points, columns=["x","y","z"])
    df["label"] = labels
    df["label_new"] = df["label"]

    # ========================
    # PROCESAR POSTES
    # ========================
    postes_info = []
    poste_points_all = df[df["label"] == LABEL_POSTE][["x","y","z"]].to_numpy()

    if len(poste_points_all) > 0:
        clustering = DBSCAN(eps=EPS_CLUSTER, min_samples=MIN_SAMPLES).fit(poste_points_all)
        labels_cluster = clustering.labels_
        poste_idx = df[df["label"] == LABEL_POSTE].index.to_numpy()

        for cluster_id in np.unique(labels_cluster):
            if cluster_id == -1:
                continue  # ruido
            cluster_mask = (labels_cluster == cluster_id)
            cluster_points = poste_points_all[cluster_mask]
            altura, cx, cy, radio = medir_poste(cluster_points)

            if altura > ALTURA_UMBRAL:
                etiqueta_poste = LABEL_MT_POSTE
                tipo_poste = "MT"
            else:
                etiqueta_poste = LABEL_BT_POSTE
                tipo_poste = "BT"

            postes_info.append({
                "cluster_id": cluster_id,
                "altura": altura,
                "cx": cx,
                "cy": cy,
                "radio": radio,
                "tipo": tipo_poste,
                "etiqueta": etiqueta_poste
            })

            df.loc[poste_idx[cluster_mask], "label_new"] = etiqueta_poste

    postes_info = pd.DataFrame(postes_info)

    # ========================
    # PROCESAR CABLES
    # ========================
    cables_df = df[df["label"] == LABEL_CABLE].copy()
    if len(cables_df) > 0 and len(postes_info) > 0:
        tipos_cables = asignar_cable(postes_info, cables_df[["x","y","z"]].to_numpy())
        etiquetas_cables = np.where(tipos_cables == "MT", LABEL_MT_CABLE, LABEL_BT_CABLE)
        df.loc[cables_df.index, "label_new"] = etiquetas_cables

    # ========================
    # GUARDAR PLY CON NUEVAS ETIQUETAS
    # ========================
    new_vertex = vertex.copy()
    new_vertex[label_field] = df["label_new"].to_numpy(dtype=np.int32)
    el = PlyElement.describe(new_vertex, 'vertex')
    PlyData([el], text=False).write(output_ply)

    # ========================
    # GUARDAR EXCEL DE POSTES
    # ========================
    postes_info.to_excel(postes_xlsx, index=False, engine='openpyxl')
    
    print(f"[OK] Procesado. PLY: {output_ply}, Postes: {postes_xlsx}")