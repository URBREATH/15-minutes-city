from utilityScript import create_unique_bbox
from utilityScript import download
from utilityScript import computo
from utilityScript import save_output
import pandas as pd
import sys
import time
from time import ctime
from ast import literal_eval
import os
from enum import Enum
from parameters import read_param   

class PostDownloadMode(Enum):
    AS_IS = 0
    ONLY_A = 1
    A_B_C = 2

try:
    if len(sys.argv) != 2:
        raise ValueError("Usage: script.py <parameters_file>")

    parameters_file = sys.argv[1]
    print("Reading configuration parameters from:", parameters_file)

    common_parameters = read_param(parameters_file, 'common')

    bbox = common_parameters.get('bbox')
    outputPath = common_parameters.get('outputPath').strip()


    weight = common_parameters.get('weight', 'time')
    category = common_parameters.get('category', 'all')
    by = common_parameters.get('by', 'foot')
    city_name = common_parameters.get('city_name', '')
    clip_layer_path = common_parameters.get('clip_layer_path', None)
    # Flag origine:
    # True = i gate sono forniti dall’esterno
    # False = i gate vanno determinati automaticamente (OSM)
    flag_or = bool(common_parameters.get('flag_or', True))
    gate_path = common_parameters.get('gate_path')
    gate_path = gate_path.strip() if gate_path is not None else None


    # Traduzione in Enum per flag_post_download
    # AS_IS = uso i gate così come sono
    # ONLY_A = verifico solo quelli di tipo A
    # A_B_C = integro A, B e C
    post_map = {
        "asis": PostDownloadMode.AS_IS,
        "a": PostDownloadMode.ONLY_A,
        "abc": PostDownloadMode.A_B_C
    }
    flag_post_download = post_map.get(
        str(common_parameters.get('flag_post_download', 'a')).strip().lower(),
        PostDownloadMode.ONLY_A
    )

except Exception as e:
    print("ERROR: Script execution not started.")
    print("Error when reading configuration parameters.")
    print(e)
    sys.exit(1)


print('Working area: {}.\n'.format(os.getcwd()), flush=True)
print("Script starts.\n", flush = True)
result_bbox = create_unique_bbox(bbox, outputPath, category)

if result_bbox == 0:
    print("Unique tile created.\n", flush=True)
    
    # Legge il file appena creato
    bbox_file = f"{outputPath}/unique_bbox.csv"
    tile = pd.read_csv(bbox_file, sep=';', header=0)
    print("File unique_bbox.csv caricato correttamente.\n", flush=True)
    
    
else:
    print("Error during the first step.\n", flush=True)
    tile = pd.DataFrame() 



a = time.time()

print('DOWNLOAD starts.\n', flush=True)

bbox_tassello = tile.at[0, 'downloadBBox']  # oppure tile.iat[0, 1]

missing = 1 - download(
    bbox_tassello,
    outputPath,
    
    category,
    by,
    weight,
    flag_or,
    flag_post_download,
    gate_path
)

while missing != 0:
    time.sleep(3)
    missing = 1 - download(
        bbox_tassello,
        outputPath,
        
        category,
        by,
        weight,
        flag_or,
        flag_post_download,
        gate_path
    )

print('DOWNLOAD end.\n', flush=True)

b = time.time()
print("Time seconds for download:", b - a, flush=True)
print("Time minutes for download: {}\n".format((b - a) / 60), flush=True)

# ---------------------------------------------------------------------------------
# COMPUTO
# ---------------------------------------------------------------------------------
a = time.time()

print("COMPUTO starts.\n", flush=True)
print('----------------------------------------------------------------------------------------------------------------', flush=True)

result_computo = computo(
    bbox_tassello,
    tile.at[0, 'latCella'],
    tile.at[0, 'lonCella'],
    tile.at[0, 'raggio'],
    outputPath,
    clip_layer_path,
    city_name,
    category,
    by,
    weight
)
if result_computo == 0:
    print('----------------------------------------------------------------------------------------------------------------', flush=True)
    print("COMPUTO end.\n", flush=True)
else:
    print('----------------------------------------------------------------------------------------------------------------', flush=True)
    print("COMPUTO error.\n", flush=True)
    sys.exit()

b = time.time()
print("Time seconds for computo:", b - a, flush=True)
print("Time minutes for computo: {}\n".format((b - a) / 60), flush=True)

# ---------------------------------------------------------------------------------
# MERGE / SAVE OUTPUT
# ---------------------------------------------------------------------------------
print("Save output starts.\n", flush=True)
result_save_output = save_output(outputPath, category, by)
if result_save_output == 0:
    print("Script completed.", flush=True)
else:
    print("Error during final step.\n", flush=True)
