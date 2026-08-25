#!/usr/bin/env python3
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from scipy.spatial.distance import cdist
from scipy.interpolate import splprep, splev
import plyfile

# Parámetros
LABEL_CABLE = 7
EPS_CLUSTER = 0.25
MIN_SAMPLES = 5
LONGITUD_MAX = 50.0  # metros
DIST_MAX = 3.0       # distancia máxima entre extremos para fusionar
ANGULO_MAX = 15      # grados máximo de diferencia de dirección para fusionar

# Funciones
def calcular_grosor(cable_points):
    p0, p1 = cable_points[0], cable_points[-1]
    vec = p1 - p0
    vec_norm = vec / np.linalg.norm(vec)
    diffs = cable_points - p0
    d_perp = np.linalg.norm(diffs - np.outer(np.dot(diffs, vec_norm), vec_norm), axis=1)
    return np.mean(d_perp) * 2

def ajustar_spline(cable_points):
    try:
        tck, u = splprep(cable_points.T, s=0)
        u_fine = np.linspace(0, 1, max(100, len(cable_points)*10))
        interp_points = np.array(splev(u_fine, tck)).T
        diffs = np.diff(interp_points, axis=0)
        longitud = np.sum(np.linalg.norm(diffs, axis=1))
        return interp_points, longitud
    except:
        longitud = np.linalg.norm(cable_points[-1] - cable_points[0])
        return cable_points, longitud

def calcular_apertura(cable_points):
    p0, p1 = cable_points[0], cable_points[-1]
    vec = p1 - p0
    vec_xy = np.array([vec[0], vec[1], 0])
    vec_xy_norm = vec_xy / np.linalg.norm(vec_xy)
    diffs = cable_points - p0
    proy = diffs - np.outer(np.dot(diffs, vec_xy_norm), vec_xy_norm)
    desviacion = np.linalg.norm(proy, axis=1)
    return np.max(desviacion)

def fusionar_clusters(df_cables):
    clusters = df_cables["cluster"].unique()
    clusters = [c for c in clusters if c != -1]
    fusionados = {}
    nuevos_ids = 0
    extremos = {}

    # calcular extremos de cada cluster
    for c in clusters:
        puntos = df_cables[df_cables["cluster"]==c][["x","y","z"]].to_numpy()
        puntos = puntos[np.argsort(cdist(puntos, [puntos[0]])[:,0])]
        extremos[c] = (puntos[0], puntos[-1], puntos)

    visitados = set()
    for c1 in clusters:
        if c1 in visitados:
            continue
        visitados.add(c1)
        p1_start, p1_end, p1_pts = extremos[c1]
        merged_pts = p1_pts.copy()

        for c2 in clusters:
            if c2 in visitados:
                continue
            p2_start, p2_end, p2_pts = extremos[c2]

            # distancia mínima entre extremos
            dists = [np.linalg.norm(p1_end - p2_start),
                     np.linalg.norm(p1_end - p2_end),
                     np.linalg.norm(p1_start - p2_start),
                     np.linalg.norm(p1_start - p2_end)]
            if min(dists) < DIST_MAX:
                merged_pts = np.vstack([merged_pts, p2_pts])
                visitados.add(c2)

        fusionados[nuevos_ids] = merged_pts
        nuevos_ids += 1

    return fusionados

# Procesamiento
def procesar_cables(input_ply, output_excel, postes_excel):
    # Leer archivo de postes
    postes = pd.read_excel(postes_excel, engine='openpyxl')
    # Crear columna numérica label_new: 13 = MT, 14 = BT
    postes["label_new"] = postes["tipo"].apply(lambda x: 13 if x.upper() == "MT" else 14)

    # Leer PLY
    plydata = plyfile.PlyData.read(input_ply)
    vertex = plydata['vertex'].data
    if 'scalar_Label' not in vertex.dtype.names:
        raise ValueError("PLY no tiene columna 'scalar_Label'")
    labels = np.array(vertex['scalar_Label'], dtype=np.int32)
    points = np.vstack([vertex['x'], vertex['y'], vertex['z']]).T

    df_points = pd.DataFrame(points, columns=["x","y","z"])
    df_points["label"] = labels

    # Filtrar solo cables (label 7)
    df_cables = df_points[df_points["label"] == LABEL_CABLE]

    # DBSCAN para separar cables individuales
    clustering = DBSCAN(eps=EPS_CLUSTER, min_samples=MIN_SAMPLES).fit(df_cables[["x","y","z"]])
    df_cables = df_cables.copy()
    df_cables["cluster"] = clustering.labels_

    # Fusionar clusters cercanos
    cables_fusionados = fusionar_clusters(df_cables)

    resultados = []
    for cable_points in cables_fusionados.values():
        if len(cable_points) < 5:
            continue
        grosor = calcular_grosor(cable_points)
        spline_points, longitud = ajustar_spline(cable_points)
        if longitud > LONGITUD_MAX:
            continue
        apertura = calcular_apertura(spline_points)

        # Calcular centroide y asignar label_new según poste más cercano
        centroide = np.mean(cable_points, axis=0)
        distancias = np.linalg.norm(postes[["cx","cy","altura"]].to_numpy() - centroide, axis=1)
        idx_min = np.argmin(distancias)
        label_new = postes.loc[idx_min, "label_new"]

        resultados.append({
            "grosor_m": grosor,
            "longitud_m": longitud,
            "apertura_m": apertura,
            "label_new": label_new
        })

    # Reasignar cable_id consecutivo desde 0
    df_result = pd.DataFrame(resultados)
    df_result.insert(0, "cable_id", range(len(df_result)))
    df_result.to_excel(output_excel, index=False)
    print(f"[OK] Guardado en {output_excel}")