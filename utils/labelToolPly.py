import numpy as np
from plyfile import PlyData, PlyElement
import pandas as pd
import os

def writeLabeled(filename, points):
    folder = str(os.path.dirname(filename))+'/data/'

    if(not os.path.isdir(folder)):
        os.makedirs(folder)
    # Save labels in txt
    np.savetxt(folder+'labels.txt',
               points['class'], delimiter='\t', fmt='%d')
    # Read PLY file
    p = PlyData.read(filename)
    v = p.elements[0]
    # Get dataframe 
    df = pd.read_csv(folder+'labels.txt',
                     delim_whitespace=True, header=None)
    array = df.to_numpy().flatten()
    # Create an empty column named scalar_label
    a = np.empty(len(v.data), v.data.dtype.descr +
                 [('class', 'i4')])
    for name in v.data.dtype.fields:
        a[name] = v[name]
    a['class'] = array
    v = PlyElement.describe(a, 'vertex')
    p = PlyData([v])
    print("\nWritting plyFile in the following paths:")
    print("Label file => "+ folder+'labels.txt')
    print("Ply file   => "+ folder + 'labeled.ply')
    p.write(folder + 'labeled.ply')
