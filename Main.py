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
    tcl_candidate = os.path.join(base_prefix, 'lib', 'tcl8.6')
    tk_candidate = os.path.join(base_prefix, 'lib', 'tk8.6')
    if os.path.isdir(tcl_candidate):
        os.environ.setdefault('TCL_LIBRARY', tcl_candidate)
    if os.path.isdir(tk_candidate):
        os.environ.setdefault('TK_LIBRARY', tk_candidate)

import argparse
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
    parser.set_defaults(render=True, r=False, labels=14, use_open3d=False)

    opt = parser.parse_args()

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

    pc = PointCloud(
        opt_file,
        opt.point_size,
        points,
        opt.render,
        Config.labels,
        opt.r,
        resource_filename,
        viewer_type='open3d' if opt.use_open3d else 'pptk',
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
