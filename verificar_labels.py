import numpy as np
from plyfile import PlyData
import sys
from collections import Counter

# Cambiar esta ruta al archivo que querés analizar
filename = "/home/zahir/cloudannotation-master/dataset/GlobalMap/GlobalMap_labeled.ply"

try:
    print(f"📂 Leyendo archivo: {filename}")
    plydata = PlyData.read(filename)
    vertex = plydata['vertex'].data
except Exception as e:
    print(f"❌ Error al leer el archivo: {e}")
    sys.exit(1)

# Convertimos a un array numpy estructurado
try:
    points = np.array(vertex)
except Exception as e:
    print(f"❌ Error al convertir datos: {e}")
    sys.exit(1)

# Buscamos el campo correcto
if 'class' in points.dtype.names:
    label_field = 'class'
elif 'scalar_Label' in points.dtype.names:
    label_field = 'scalar_Label'
else:
    print("⚠️ El archivo no tiene un campo 'class' ni 'scalar_Label'")
    sys.exit(1)

labels = points[label_field]

# Verificamos que no haya NaN ni tipos raros
if not np.issubdtype(labels.dtype, np.integer):
    print(f"⚠️ El tipo de dato de '{label_field}' no es entero: {labels.dtype}")
    try:
        labels = labels.astype(np.int32)
        print("✅ Se convirtió a int32")
    except:
        print("❌ No se pudo convertir a enteros.")
        sys.exit(1)

# Contamos valores únicos
try:
    unique, counts = np.unique(labels, return_counts=True)
    print(f"✅ Clases encontradas en '{label_field}':")
    for u, c in zip(unique, counts):
        print(f"  Clase {u}: {c} puntos")
except Exception as e:
    print(f"❌ Error al contar clases: {e}")