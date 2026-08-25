import os
from alg import classify_poles
from alg import classify_wires


def process_patch(dataset_folder):
    for folder_name in os.listdir(dataset_folder):
        map_folder = os.path.join(dataset_folder, folder_name, "map")
        ply_labeled_path = os.path.join(map_folder, "data", "labeled.ply")
        pole_ply_labeled_path = os.path.join(map_folder, "data", "pole_labeled.ply")
        # wire_ply_labeled_path = os.path.join(map_folder, "data", "wire_labeled.ply")

        pole_xlsx_labeled_path = os.path.join(map_folder, "data", "pole_report.xlsx")
        # wire_xlsx_labeled_path = os.path.join(map_folder, "data", "wire_report.xlsx")
        if os.path.exists(ply_labeled_path):
            print(f"Processing: {ply_labeled_path}")
            classify_poles.procesar_nube(
                ply_labeled_path, pole_ply_labeled_path, pole_xlsx_labeled_path
            )
            # classify_wires.procesar_cables(pole_ply_labeled_path,wire_ply_labeled_path, )



if __name__ == "__main__":
    dataset_folder = "dataset"

    process_patch(dataset_folder)
