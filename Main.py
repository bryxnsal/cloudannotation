import argparse
from genericpath import isdir, isfile
from plyfile import PlyData
import os
import glob
import sys
import tkinter as tk
from tkinter import messagebox
import Config

parser = argparse.ArgumentParser()
parser.add_argument("folder", type=str, nargs='?', default=None, help="Input folder/file (optional, can be opened from GUI)")
parser.add_argument("--r", action="store_true")
parser.add_argument("--name", type=str, required=False, help="Resource filename")

parser.add_argument("--point_size", type=float, default=0.01, help="Point size")
# parser.add_argument('--max_points', type=int, default=10000000,
#                     help='Number of points to load from file')
parser.add_argument("--render", dest="render", action="store_true")
parser.add_argument("--no-render", dest="render", action="store_false")


parser.set_defaults(render=True, r=False, labels=14)

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
            if opt.name == None:
                list_of_files = glob.glob(advances_folder + "/*.ply")
                if len(list_of_files) == 0:
                    print("You dont have any advance file")
                    sys.exit()
                else:
                    resource_filename = max(list_of_files, key=os.path.getctime)
                    print("Openning last advance file: " + resource_filename)

            else:
                if isfile(advances_folder + opt.name):
                    resource_filename = advances_folder + opt.name
                    print("Openning advance file: " + resource_filename)
                else:
                    print("Advance file does not exist")
                    sys.exit()
        else:
            print("\n Openning original file")
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

if __name__ == "__main__":
    """
    When calling this code from command line, a PointCloud object is created with a given input file,
    and then the control of the command line is passed over to the user for an interactive session.

    The program can be called like this:
        python3 Main.py --file ~/RackSlice.las --point_size 0.05
    or:
        python3 Main.py -h

    In this session, the user can use the point cloud and its functions via pc.
    For example, the user could say:
       mask = pc.select(classes=[1,2,3], blue=range(200, 256))
       pc.render(mask)
       pc.write('~/foo.las', showing=True)

    The first line will select all the points which have class 1,2 or 3 (walls, floor, and ceiling), and a
    fairly large blue component (blue ranges from 0 to 255).
    The second line then renders only those points selected in the first line.
    The third line writes these selected points out to a new file called foo.las.

    Alternatively, the user could have selected some points using  (ctrl + left-mouse-button) drag and drop, and
    then executed:
        pc.write('~/foo.las', highlighted=True)

    This will write a new point cloud file out with only the highlighted points.

    Also note that clicking the ']' close square bracket button on the keyboard while viewing the points will
    cycle through the different color schemes of the point cloud including rgb, classes, user_data, and intensity.
    """
    import code
    from PointCloud import PointCloud
    import numpy as np
    import pandas as pd
    import knn as knn
    from Voxelize import VoxelGrid
    import pptk
    from GUI import ModernAnnotationGUI
    import queue
    import threading

     # Create a queue for communication between threads
    command_queue = queue.Queue()
   
    pc = PointCloud(
        opt_file,
        opt.point_size,
        points,
        opt.render,
        Config.labels,
        opt.r,
        resource_filename,
    )

    def run_gui():
        gui = ModernAnnotationGUI(pc)
        gui.run()

     # Start GUI in separate thread
    gui_thread = threading.Thread(target=run_gui, daemon=True)
    gui_thread.start()


    try:
        code.interact(local=locals())
    finally:
        try:
            pc.close_viewer()
        except Exception:
            pass
        import os
        os._exit(0)

