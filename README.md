# Pointcloud Annotation Tool

## Instalacion global con `uv`

El CLI requiere Python 3.8. La instalación recomendada para Linux x86_64 usa
PPTK y queda disponible globalmente como `cdann`:

```bash
# 1. Instalar uv (si no lo tienes instalado aún)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Descargar Python 3.8 y clonar el repositorio
uv python install 3.8
git clone https://github.com/bryxnsal/cloudannotation.git
cd cloudannotation

# 3. Instalar globalmente el CLI como cdann
uv tool install ".[pptk]"
```

Para reinstalar después de actualizar el repositorio (`git pull`):

```bash
uv tool install --force ".[pptk]"
```

En plataformas donde PPTK no esté disponible, instala Open3D y activa el
visor alternativo:

```
uv tool install --force ".[open3d]"
cdann ./dataset/Quanergy000 --use-open3d
```

También puedes instalar ambos visores con `uv tool install --force ".[all]"`.
El wheel PPTK está fijado por URL y SHA-256 en `pyproject.toml`; no se
descarga desde mirrors desconocidos.

## Estructura y Manejo de Archivos

Al ejecutarse como CLI global (`cdann`), la herramienta es **completamente flexible con las rutas**:

1. **Archivos sueltos en cualquier directorio**: Puedes abrir directamente cualquier archivo `.ply`, `.las` o `.pcd` ubicado en cualquier carpeta de tu equipo (`cdann mi_nube.ply`).
2. **Generación automática de avances (`advances/`)**: Al guardar un avance (`Ctrl + S` o botón *Save Advance*), `cdann` creará automáticamente la subcarpeta `advances/` al lado de tu archivo si no existe.
3. **Inicio sin argumentos**: Si ejecutas `cdann` sin parámetros, abrirá la interfaz gráfica permitiéndote cargar cualquier nube con el botón **"Open PLY"** (`Ctrl + O`).

### Organización por carpetas de proyecto (Opcional):

Para proyectos organizados por lotes o escaneos, se sugiere la siguiente convención:

```
proyecto_escaneo/
├── mi_nube.ply              -- Nube de puntos original de entrada
├── data/                    -- Opcional: exportaciones finales o etiquetas txt
└── advances/                -- Creada automáticamente al guardar avances
    ├── GlobalMap_20260907_120000.ply
    └── carretera_labeled.ply
```

## Ejecucion

Al ejecutar el PLY se debera abrir un visor y dentro del terminal
podremos ejecutar codigo para manipular la nube de puntos.

```
cdann [folderName]
```

Argumentos principales:
+ `folder`            -- Carpeta o archivo PLY a cargar (opcional, se puede abrir desde la GUI con "Open PLY")
+ `--point_size`      -- Tamaño de los puntos [Por defecto: 0.01]
+ `--use-open3d`      -- Usar visor moderno Open3D en lugar de PPTK
+ `--r`               -- Modo recovery [Abre el último avance en vez del archivo original]
+ `--name`            -- Especifica el archivo en el modo recovery a usar

**Ejemplo en modo normal (PPTK):**

```bash
cdann ./dataset/Quanergy000/Quanergy000.ply --point_size 0.03
```

**Ejemplo con visor Open3D:**

```bash
cdann ./dataset/Quanergy000/Quanergy000.ply --use-open3d
```

**Ejemplo con modo recovery:**

Usar el siguiente comando para obtener el último avance:

```bash
cdann ./dataset/Quanergy000 --point_size 0.03 --r
```

Usar el siguiente comando para obtener el último avance por nombre:

```bash
cdann ./dataset/Quanergy000 --point_size 0.03 --r --name road.ply
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
- Tecla 7               -- Vista superior (PPTK)
- Tecla 5               -- Cambiar perpectiva (PPTK)
- Tecla 3, 1            -- Vistas laterales (PPTK)
```

**Atajos de Clasificación Contextuales (Directos en el Visor 3D y en la GUI):**
Los atajos de teclado (`1`-`9`, `q`, `w`, `e`, etc.) funcionan **directamente dentro del visor 3D (PPTK u Open3D)** sin necesidad de hacer clic sobre la GUI:
- **Con puntos seleccionados (`Ctrl + Drag`)**: Al presionar una tecla de atajo (ej. `1` para *Suelo*, `2` para *Vegetación*, o letras configuradas), los puntos seleccionados se clasifican y colorean inmediatamente.
- **Sin puntos seleccionados en PPTK**: Las teclas `1`-`9` preservan su comportamiento nativo de cámara (Superior, Frontal, Lateral, etc.), mientras que las teclas alfabéticas o el panel GUI seleccionan la clase activa.
- **Personalización**: Puedes reasignar o activar/desactivar cualquier atajo pulsando el botón **"Shortcuts"** en la GUI.

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


## Atajos de teclado en la GUI

La aplicación cuenta con atajos configurables globalmente en la GUI (accesibles con la tecla `F1`):

| Atajo | Acción |
| :--- | :--- |
| `Ctrl + S` | Guardar avance (`Save Advance`) |
| `Ctrl + Z` | Deshacer clasificación (`Undo`) |
| `Ctrl + Y` | Rehacer clasificación (`Redo`) |
| `Ctrl + O` | Abrir archivo PLY / LAS (`Open PLY`) |
| `Ctrl + D` | Deseleccionar puntos (`Unselect`) |
| `Ctrl + I` | Invertir selección activa |
| `1` .. `9`, `0` | Asignar clase rápida a la selección |
| `F1` | Abrir modal de Atajos y Personalización |
| `Espacio` | Re-renderizar / Refrescar vista |

---

## Solución de problemas comunes

### 1. Error de librería `libtbb.so.2` al usar PPTK en sistemas Linux limpios
Si en una máquina nueva PPTK no encuentra `libtbb`, instálala desde los repositorios del sistema:
```bash
sudo apt update && sudo apt install -y libtbb-dev
```

### 2. Alternativa rápida sin depender de drivers o librerías de PPTK
Si no deseas instalar librerías adicionales del sistema, puedes ejecutar directamente con el visor Open3D:
```bash
cdann --use-open3d
```
