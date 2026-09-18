import os
import sys

# Auto-patch for standalone CPython / X11 XCB sequence assertion compatibility on Linux
if sys.platform.startswith('linux') and 'CDANN_COMPAT_ACTIVE' not in os.environ:
    import subprocess
    helper_dir = os.path.expanduser('~/.local/share/cloudannotation/lib')
    so_path = os.path.join(helper_dir, 'libcloudannotation_x11_compat.so')
    if not os.path.isfile(so_path):
        try:
            os.makedirs(helper_dir, exist_ok=True)
            c_path = os.path.join(helper_dir, 'compat.c')
            with open(c_path, 'w') as f:
                f.write(
                    '#define _GNU_SOURCE\n'
                    '#include <dlfcn.h>\n'
                    '#include <string.h>\n\n'
                    'void* dlopen(const char *filename, int flags) {\n'
                    '    static void* (*real_dlopen)(const char*, int) = NULL;\n'
                    '    if (!real_dlopen) {\n'
                    '        real_dlopen = dlsym(RTLD_NEXT, "dlopen");\n'
                    '    }\n'
                    '    if (filename && strstr(filename, "libXcursor")) {\n'
                    '        return NULL;\n'
                    '    }\n'
                    '    return real_dlopen(filename, flags);\n'
                    '}\n'
                )
            subprocess.run(['gcc', '-shared', '-fPIC', '-O2', '-o', so_path, c_path, '-ldl'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    if os.path.isfile(so_path):
        os.environ['CDANN_COMPAT_ACTIVE'] = '1'
        existing = os.environ.get('LD_PRELOAD', '')
        os.environ['LD_PRELOAD'] = f'{so_path}:{existing}'.strip(':')
        os.execv(sys.executable, [sys.executable] + sys.argv)

# Auto-configure TCL_LIBRARY and TK_LIBRARY for portable Python distributions (e.g., uv managed CPython)
if 'TCL_LIBRARY' not in os.environ or 'TK_LIBRARY' not in os.environ:
    base_prefix = getattr(sys, 'base_prefix', sys.prefix)
    tcl_candidates = [
        os.path.join(base_prefix, 'lib', 'tcl8.6'),
        os.path.join(base_prefix, 'tcl', 'tcl8.6'),
    ]
    tk_candidates = [
        os.path.join(base_prefix, 'lib', 'tk8.6'),
        os.path.join(base_prefix, 'tcl', 'tk8.6'),
    ]
    for cand in tcl_candidates:
        if os.path.isdir(cand):
            os.environ.setdefault('TCL_LIBRARY', cand)
            break
    for cand in tk_candidates:
        if os.path.isdir(cand):
            os.environ.setdefault('TK_LIBRARY', cand)
            break

import argparse
import platform
import shutil
import subprocess
from genericpath import isdir, isfile
from plyfile import PlyData
import glob
import tkinter as tk
from tkinter import messagebox
import queue
import threading
import code


import Config
from PointCloud import PointCloud
from GUI import ModernAnnotationGUI


def main():
    parser = argparse.ArgumentParser(prog="cdann", description="CloudAnnotation CLI tool")
    parser.add_argument("folder", type=str, nargs='?', default=None, help="Input folder/file (optional, can be opened from GUI)")
    parser.add_argument("--r", action="store_true")
    parser.add_argument("--name", type=str, required=False, help="Resource filename")
    parser.add_argument("--point_size", type=float, default=0.01, help="Point size")
    parser.add_argument("--render", dest="render", action="store_true")
    parser.add_argument("--no-render", dest="render", action="store_false")
    parser.add_argument("--use-open3d", dest="use_open3d", action="store_true", help="Use Open3D as 3D visualizer instead of PPTK")
    parser.add_argument("--use-vispy", dest="use_vispy", action="store_true", help="Use VisPy (OpenGL Turntable) as 3D visualizer instead of PPTK")
    parser.add_argument("--use-pyvista", dest="use_pyvista", action="store_true", help="Use PyVista (VTK Terrain) as 3D visualizer instead of PPTK")
    parser.add_argument("--sysinfo", "-sysinfo", dest="sysinfo", action="store_true", help="Display system information, environment, 3D viewers and GPU drivers")
    parser.set_defaults(render=True, r=False, labels=14, use_open3d=False, use_vispy=False, use_pyvista=False, sysinfo=False)

    opt = parser.parse_args()

    if opt.sysinfo:
        print("=" * 62)
        print("            CloudAnnotation (cdann) - System Info")
        print("=" * 62)
        print(f"OS:               {platform.system()} {platform.release()} ({platform.machine()})")

        # Display server environment
        if sys.platform.startswith('win32'):
            disp_str = "Windows DWM (Desktop Window Manager)"
        else:
            session_type = os.environ.get('XDG_SESSION_TYPE', '')
            disp_var = os.environ.get('DISPLAY', '')
            wayland_var = os.environ.get('WAYLAND_DISPLAY', '')
            disp_info = []
            if session_type:
                disp_info.append(session_type)
            if disp_var:
                disp_info.append(f"DISPLAY={disp_var}")
            if wayland_var:
                disp_info.append(f"WAYLAND={wayland_var}")
            disp_str = " ".join(disp_info) if disp_info else "Headless / Unknown"
        print(f"Display Server:   {disp_str}")

        # CPU Cores
        cpu_cores = os.cpu_count() or "Unknown"
        print(f"CPU Cores:        {cpu_cores} logical threads")

        # RAM info (Windows via ctypes MEMORYSTATUSEX, Linux via /proc/meminfo)
        ram_str = "Unknown"
        if sys.platform.startswith('win32'):
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total_gb = stat.ullTotalPhys / (1024 ** 3)
                    avail_gb = stat.ullAvailPhys / (1024 ** 3)
                    ram_str = f"{total_gb:.1f} GB total ({avail_gb:.1f} GB available)"
            except Exception:
                pass
        elif os.path.isfile('/proc/meminfo'):
            try:
                with open('/proc/meminfo') as f:
                    meminfo = {line.split(':')[0]: int(line.split(':')[1].strip().split()[0]) for line in f}
                    total_gb = meminfo.get('MemTotal', 0) / (1024 * 1024)
                    avail_gb = meminfo.get('MemAvailable', 0) / (1024 * 1024)
                    ram_str = f"{total_gb:.1f} GB total ({avail_gb:.1f} GB available)"
            except Exception:
                pass
        print(f"RAM:              {ram_str}")

        print(f"Python:           {platform.python_version()} ({sys.executable})")

        # Tkinter GUI status
        try:
            import tkinter
            tk_ver = tkinter.TkVersion
            tk_status = f"Tk {tk_ver} [OPERATIONAL]"
        except Exception as e:
            tk_status = f"Unavailable ({e})"
        print(f"Tkinter GUI:      {tk_status}")

        try:
            import importlib.metadata as meta
            cdann_ver = meta.version('cloudannotation')
        except Exception:
            cdann_ver = '0.3.1'
        print(f"cdann version:    {cdann_ver}")

        # Default viewer determination
        if sys.platform.startswith('win32'):
            default_viewer = "vispy (Windows fallback: pyvista, open3d)"
        else:
            default_viewer = "pptk (Linux default; alternatives: --use-pyvista, --use-vispy, --use-open3d)"
        print(f"Default Viewer:   {default_viewer}")

        print("-" * 62)
        print("3D Viewers & Core Dependencies:")

        libs = [
            ('pptk', 'pptk'),
            ('pyvista', 'pyvista'),
            ('vtk', 'vtk'),
            ('vispy', 'vispy'),
            ('glfw', 'glfw'),
            ('PyQt5', 'PyQt5'),
            ('open3d', 'open3d'),
            ('numpy', 'numpy'),
            ('pandas', 'pandas'),
            ('laspy', 'laspy'),
            ('plyfile', 'plyfile'),
        ]
        for name, mod_name in libs:
            try:
                m = __import__(mod_name)
                ver = getattr(m, '__version__', None)
                if ver is None and mod_name == 'vtk':
                    ver = getattr(m, 'vtkVersion', None)
                    if ver:
                        ver = ver.GetVTKVersion()
                ver_str = str(ver) if ver else 'Installed'
                print(f"  {name:<14} {ver_str:<18} [AVAILABLE]")
            except Exception:
                print(f"  {name:<14} {'Not installed':<18} [NOT AVAILABLE]")

        print("-" * 62)
        print("Graphics & OpenGL Hardware:")
        gl_found = False

        # 1. On Windows: Query GPU via PowerShell / WMIC
        if sys.platform.startswith('win32'):
            try:
                ps_cmd = 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Caption'
                res = subprocess.run(['powershell', '-NoProfile', '-Command', ps_cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4)
                gpus = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                for gpu in gpus:
                    print(f"  GPU Device:     {gpu}")
                    gl_found = True
            except Exception:
                pass

        # 2. Linux: Query glxinfo
        if not gl_found and shutil.which('glxinfo'):
            try:
                res = subprocess.run(['glxinfo'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
                for line in res.stdout.splitlines():
                    if any(k in line for k in ['OpenGL vendor', 'OpenGL renderer', 'OpenGL version', 'OpenGL shading language']):
                        print("  " + line.strip())
                        gl_found = True
            except Exception:
                pass

        # 3. Cross-platform: Query nvidia-smi if available
        if shutil.which('nvidia-smi'):
            try:
                res = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        if line.strip():
                            print("  NVIDIA Driver:  " + line.strip())
                            gl_found = True
            except Exception:
                pass

        # 4. Cross-platform: Try reading OpenGL renderer string via PyQt5 or VisPy if available
        if not gl_found:
            try:
                from PyQt5.QtWidgets import QApplication
                from PyQt5.QtGui import QOpenGLContext, QSurfaceFormat
                app = QApplication.instance() or QApplication([])
                ctx = QOpenGLContext()
                fmt = QSurfaceFormat()
                ctx.setFormat(fmt)
                if ctx.create():
                    print(f"  OpenGL Profile: Qt5 OpenGL {ctx.format().majorVersion()}.{ctx.format().minorVersion()}")
                    gl_found = True
            except Exception:
                pass

        if not gl_found:
            print("  Could not query GPU details automatically.")
        print("=" * 62)
        return

    resource_filename = ""
    opt_file = None
    points = 0

    if opt.folder:
        is_folder = os.path.isdir(opt.folder)

        if is_folder:
            opt_file = os.path.join(opt.folder, "map", "GlobalMap.ply")
            advances_folder = os.path.join(opt.folder, "map", "advances")
            if opt.r:
                print("\nRecovery mode was set:")
                if opt.name is None:
                    list_of_files = glob.glob(advances_folder + "/*.ply")
                    if len(list_of_files) == 0:
                        print("You dont have any advance file")
                        sys.exit(1)
                    else:
                        resource_filename = max(list_of_files, key=os.path.getctime)
                        print("Opening last advance file: " + resource_filename)
                else:
                    if isfile(advances_folder + opt.name):
                        resource_filename = advances_folder + opt.name
                        print("Opening advance file: " + resource_filename)
                    else:
                        print("Advance file does not exist")
                        sys.exit(1)
            else:
                print("\nOpening original file")
        else:
            opt_file = opt.folder

        if os.path.isfile(opt_file):
            p = PlyData.read(opt_file)
            points = p.elements[0].count
            print("\nPoints: " + str(points))
        print("Labels: " + str(len(Config.labels)))
    else:
        print("\nNo PLY file specified at launch. Use the 'Open PLY' button in the GUI to load a point cloud.")
        print("Labels: " + str(len(Config.labels)))

    command_queue = queue.Queue()

    # Determine 3D viewer engine: PyVista > VisPy > Open3D > PPTK (with Windows defaulting to VisPy/PyVista)
    if opt.use_pyvista:
        chosen_viewer = 'pyvista'
    elif opt.use_vispy:
        chosen_viewer = 'vispy'
    elif opt.use_open3d:
        chosen_viewer = 'open3d'
    elif sys.platform.startswith('win32'):
        # On Windows PPTK binary wheel is unavailable; prefer VisPy/PyVista
        chosen_viewer = 'vispy'
    else:
        chosen_viewer = 'pptk'

    pc = PointCloud(
        opt_file,
        opt.point_size,
        points,
        opt.render,
        Config.labels,
        opt.r,
        resource_filename,
        viewer_type=chosen_viewer,
    )

    gui = ModernAnnotationGUI(pc)

    def run_console():
        try:
            # Interactive shell in daemon thread
            env_locals = dict(locals())
            env_locals.update({'pc': pc, 'gui': gui, 'PointCloud': PointCloud})
            code.interact(local=env_locals)
        except Exception:
            pass

    console_thread = threading.Thread(target=run_console, daemon=True)
    console_thread.start()

    try:
        gui.run()
    finally:
        try:
            pc.close_viewer()
        except Exception:
            pass
        os._exit(0)


if __name__ == "__main__":
    main()
