# Pointcloud Annotation Tool

## Instalacion [Local Python]

Pon tus archivos en la carpeta dataset [Recomendacion]:

```
git clone https://gitlab.com/Moises981/cloudannotation
cd cloudannotation
pip3 install -r requirements.txt
mkdir dataset
```

## Instalacion [Conda env]
Pon tus archivos en la carpeta dataset [Recomendacion]:

```
conda create -n pcd  python=3.6
conda activate pcd 
pip install -r requirements.txt
mkdir dataset
```

## Estructura de la carpeta

Solo las siguientes carpetas/archivos son requeridos:
+ dataset Folder
+ [filename] Folder 
+ [filename].ply

Lo demás es generado por automaticamente por codigo.

```
dataset Folder                  -- Carpeta principal
└── [filename] Folder           -- Carpeta nombrada de acuerdo al nombre del archivo
    ├── [filename].ply          -- Archivo de entrada
    ├── data                    -- Carpeta que almacena los labels
    │   ├── labeled.ply         -- Archivo Ply original con los labels
    │   └── labels.txt          -- Archivo Txt con solamente labels
    └── advances                -- Carpeta que almacena avances [Write method]
        └── [customName].ply    -- Nombre del archivo personalizado [Write method]
```

## Ejecucion

Al ejecutar el PLY se debera abrir un visor y dentro del terminal
podremos ejecutar codigo para manipular la nube de puntos.

```
python3 Main.py [folderName]
```

Argumentos principales:
+ --point_size      -- Tamaño de los puntos [Por defecto es: 0.01]
+ --r               -- Usar modo recovery [Abre el ultimo avance en vez del archivo original]
+ --name            -- Especifica el archivo en el modo recovery a usar
+ --labels          -- Especifica la cantidad de labels [Por defecto es: 9]


**Ejemplo en modo normal:**

```
python3 Main.py --file ./dataset/Quanergy000/Quanergy000.ply  --point_size 0.03
```

**Ejemplo con modo recovery:**

Usar el siguiente comando para obtener el ultimo avance:

```
python3 Main.py ./dataset/Quanergy000  --point_size 0.03 --r
```

Usar el siguiente comando para obtener el ultimo avance por nombre:

```
python3 Main.py ./dataset/Quanergy000  --point_size 0.03 --r --name road.ply
```

**Estructura del archivo:**

```
dataset/            
└── Quanergy000/        
    ├── Quanergy000.ply          
    ├── data                 
    │   ├── labeled.ply      
    │   └── labels.txt        
    └── advances               
        └── road.ply   
```


## Flujo de trabajo

**Combinaciones de Teclas:**

```
- Clic Izquierdo        -- Rotar alrededor
- Ctrl + Clic Izquierdo -- Seleccionar puntos dentro del rectangulo
- Tecla 7               -- Vista superior
- Tecla 5               -- Cambiar perpectiva
- Tecla 3 ,1            -- Vistas laterales
```

**Comandos en el terminal:**

```
pc.points['class']                      => Acceder a la clase de los puntos
pc.write('example.ply',overwrite=True)  => Sobreescribir archivo con labels
pc.render()                             => Renderiza toda la nube de puntos en el visor
pc.render(highlighted=True)             => Renderiza solo lo que esta seleccionado [Util para filtrar]
pc.classify([label],overwrite=True)     => Clasificar los puntos como un label
```

Mas informacion aqui: https://github.com/bradylowe/pptk_annotation_tool

**Commandos personalizados:**

```
pc.render(highlighted=True,invert=True) => Renderiza lo que no esta seleccionado [Antes de llamar ejecutar pc.render()]
pc.writeLabels()                        => Escribe dos archivos en formato ['[filename]_labeled.ply','labels.txt']
pc.labelIsEmpty([label])                => Muestra si un label esta vacio
pc.clearLabel([label])                  => Resetea a cero un label [Util para limpiar labels al inicio]
pc.move([label_1],[label_2])            => Desplazar un canal label a otro
pc.renderLabel([Arreglo de enteros])    => Renderiza solo los labels dentro del array. Ej: [1,2,3,4]
pc.save()                               => Save advances
pc.export()                             => Export result
```

Nota:

- labels.txt almacena solamente los labels en formato txt.
- [filename]\_labeled.ply crea un PLY similar al original pero con labels

# Intuicion:

[![3D Point Cloud Annotation Tool Demo](https://img.youtube.com/vi/3pG60swmxvM/0.jpg)](https://www.youtube.com/watch?v=3pG60swmxvM "E3D Point Cloud Annotation Tool Demo")

# Explicacion del canal RGB [Importante]

El PLY con data XYZRGB se vera afectado de la siguiente manera al trabajar:
Los canales RGB son procesados antes de mostrarse en el visor.
Cada canal de color posee un tipo :

- Canal R: Arreglo de class [Labels]
- Canal G: Arreglo de user_data
- Canal B: Arreglo de information
  Escribir "pc.points" en el terminal para ver los tipos de datos.

Esta es la razon por la cual la data al ingresar no se muestra en RGB sino en otros colores

Al ingresar podra observar que la nube de puntos tendra varias colores dispersos eso se debe a que el canal "class" divide todo el canal Rojo entre la cantidad de labels, por lo tanto cada punto tendra una etiqueta ya definida.

# Recomendaciones

Se recomienda trabajar por canal en canal en este orden, ejemplo si los labels son:

```
Unclassified    => label 0
Ground          => label 1
Sidewalk        => label 2
Road            => label 3
Buildings       => label 4
Vegetation      => label 5
Poles           => label 6
Wires           => label 7
Cars            => label 8
Advertisements  => label 9
Monumental      => label 10
Signs           => label 11
```

Proposal:


Teniendo la pista y la parte de abajo hecha , los cables seran mas facil de segmentar.

Se recomienda guardar por cada label finalizado.
Se recomienda limpiar el label a trabajar con "pc.clearLabel([label])"

# Guardar avance

Escribe en el terminal:

```
pc.write('road_labeled.ply',overwrite=True)
```


# Problemas de instalacion

## El archivo PLY no carga [Python Local]

Ejecutar los siguientes comandos:

```
cd ~/.local/lib/python2.7/site-packages/pptk/libs/
mv libz.so.1 libz.so.1.old
sudo ln -s /lib/x86_64-linux-gnu/libz.so.1
```

## El archivo PLY no carga [Conda env]
```
cd ~/anaconda3/envs/pcd/lib/python3.6/site-packages/pptk/libs/
mv libz.so.1 libz.so.1.old
sudo ln -s /lib/x86_64-linux-gnu/libz.so.1
```
