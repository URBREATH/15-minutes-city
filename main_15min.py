import sys
import os
import time
from datetime import datetime
import pandas as pd
import json
from scripts.errors import raise_error

from scripts.index_processing import create_unique_bbox, download, computo
from scripts.parameters import read_param, section_exists_and_has_fields

import warnings
warnings.filterwarnings("ignore")

# ------------------------------------------------
# UTILITY FUNCTIONS
# ------------------------------------------------
def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def print_start(msg):
    print(f"[{ts()}] {msg}", flush=True)
    print("---------------------------------------------------------------------------------------------", flush=True)
    return time.time()

def print_end(msg, t0, t_start_dt):
    t_end_dt = datetime.now()
    dt = time.time() - t0
    dt_dt = (t_end_dt - t_start_dt).total_seconds()

    print("---------------------------------------------------------------------------------------------", flush=True)
    print(
        f"[{ts()}] FINE {msg} "
        f"(Durata: {dt:.2f}s = {dt/60:.2f}m = {dt/3600:.2f}h) ",
        flush=True
    )
    return dt



def validate_parameters(parameters_file):

    # ---------------- AOI ----------------
    aoi_parameters = read_param(parameters_file, 'aoi')
    # ---------------- EXECUTION ----------------

    execution_parameters = read_param(parameters_file, 'execution')

    required_aoi = ['bbox','name']
    required_execution = ['outputpath']
    
    missing_fields = []
    
    # Controlla AOI
    if not section_exists_and_has_fields(parameters_file, 'aoi', required_aoi):
        for field in required_aoi:
            missing_fields.append(f"aoi_{field}")
    
    # Controlla Execution
    
    if not section_exists_and_has_fields(parameters_file, 'execution', required_execution):
        for field in required_execution:
            missing_fields.append(field)
    
    if missing_fields:
        raise_error("ERR_002", extra="aoi_bbox | aoi_name | execution_outputPath")


    weight = aoi_parameters.get('weight') or 'time'
    if weight not in ["time","distance"]:
        raise_error("ERR_004", extra="time | distance")

    mode = aoi_parameters.get('mode') or 'walk'
    if mode not in ["walk","bike"]:
        raise_error("ERR_005", extra="walk | bike")


    # ---------------- POI ----------------
    try:
        poi_parameters = read_param(parameters_file, 'poi')
    except:
        poi_parameters =  {}    
    poi_category_osm = poi_parameters.get('poi_category_osm') 
    poi_category_custom_name = poi_parameters.get('poi_category_custom_name')
    poi_category_custom_csv = poi_parameters.get('poi_category_custom_csv')


    with open("osm_categories_tag.json", "r", encoding="utf-8") as f:
        osm_tags = json.load(f)
            
    # Valid OSM categories
    valid_poi_category_osm = set(osm_tags.keys()) | {"all"}
    
    if poi_category_osm and poi_category_osm not in valid_poi_category_osm:
        raise_error(
            "ERR_006",
            extra=f"{'| '.join(valid_poi_category_osm)}"
        )
    # Validate custom POI
    custom_names = ["".join(x.lower().split()) for x in poi_category_custom_name.split(",")] if poi_category_custom_name else []
    custom_csvs = [x.strip() for x in poi_category_custom_csv.split(",")] if poi_category_custom_csv else []

    conflicting_custom = [name for name in custom_names if name in valid_poi_category_osm]
    if conflicting_custom:
        raise_error(
            "ERR_007",
            extra="custom category cannot match OSM category"
        )
    
    if custom_names or custom_csvs:
        if len(custom_names) != len(custom_csvs):
            raise_error("ERR_008", extra ="custom categories count must match CSV categories counth")
       
    # ---------------- PARK ----------------
    try:
        park_parameters = read_param(parameters_file, 'park')
    except:
        park_parameters =  {}
    park_source = park_parameters.get('park_gates_source') or 'osm'
    valid_park_source = ["osm", "csv", "road_intersect", "virtual"]
    if park_source not in valid_park_source:
        raise_error("ERR_009", extra=f"{'| '.join(valid_park_source)}")


    park_csv = park_parameters.get('park_gates_csv_path', '').strip()

    if park_source == "csv":

        if not park_csv:
            raise_error("ERR_010", extra=park_csv)
        
        if not os.path.isfile(park_csv):
            raise_error("ERR_010", extra=park_csv)
    
    if custom_names or custom_csvs:
        for f in custom_csvs:
            if not os.path.exists(f):
                raise_error("ERR_011", extra=f)

    clip_layer_path = aoi_parameters.get('clip_layer_path')
    if clip_layer_path and not os.path.exists(clip_layer_path):
        raise_error("ERR_012", extra=clip_layer_path)
        
    # ---------------- GRID ----------------
    try:
        grid_parameters = read_param(parameters_file, 'grid')
    except:
        grid_parameters =  {}
    grid_path = grid_parameters.get('grid_path')
    if grid_path and not os.path.exists(grid_path):
        raise_error("ERR_013", extra=grid_path)


    return {
        "aoi": aoi_parameters,
        "poi": poi_parameters,
        "park": park_parameters,
        "grid": grid_parameters,
        "execution": execution_parameters
    }

# ------------------------------------------------
# MAIN SCRIPT
# ------------------------------------------------


if (
    len(sys.argv) != 2
    or not sys.argv[1].strip()
    or not os.path.exists(sys.argv[1])
):
    raise_error(
        "ERR_001",
        extra=sys.argv[1] if len(sys.argv) > 1 else ""
    )

parameters_file = sys.argv[1]
print(f"Reading configuration parameters from: {parameters_file}", flush=True)

script_start_time = datetime.now()
print("=============================================================================================", flush=True)
print(f"[{ts()}] SCRIPT STARTS\n", flush=True)

# ---------------- VALIDATE ALL PARAMETERS ----------------
params = validate_parameters(parameters_file)

aoi = params["aoi"]
grid = params["grid"]
execution = params["execution"]
poi = params["poi"]
park = params["park"]

# ---------------- CREATE UNIQUE BBOX ----------------
result_bbox = create_unique_bbox(eval(aoi['bbox']), execution['outputpath'], float(grid.get('hex_diameter_m') or 250))


# Read unique_bbox
bbox_file = os.path.join(execution['outputpath'], "unique_bbox.csv")
tile = pd.read_csv(bbox_file, sep=';', header=0)
print("File unique_bbox.csv uploaded successfully.\n", flush=True)

# ---------------- DOWNLOAD ----------------
t0_download = print_start("DOWNLOAD")
t_start_download = datetime.now()


bbox_tassello = tile.at[0,'downloadBBox']

poi_category_custom_name = poi.get('poi_category_custom_name')
poi_category_custom_csv = poi.get('poi_category_custom_csv')

custom_names = ["".join(x.lower().split()) for x in poi_category_custom_name.split(",")] if poi_category_custom_name else []
custom_csvs = [x.strip() for x in poi_category_custom_csv.split(",")] if poi_category_custom_csv else []

poi_category_osm = poi.get('poi_category_osm')
if not poi_category_osm and not custom_names:
    poi_category_osm = 'all'
    
if not os.path.exists(execution['outputpath'].strip()):
    raise_error("ERR_003")
        
missing = 1 - download(

    bbox_tassello,
    execution['outputpath'],
    custom_names,
    custom_csvs,
    poi_category_osm,
    aoi.get('mode') or 'walk',
    aoi.get('weight') or 'time',
    park.get('park_gates_source') or 'osm',
    park.get('park_gates_osm_buffer_m') or 10,
    park.get('park_gates_csv_path') or None,
    park.get('park_gates_virtual_distance_m') or 100
)


max_attempts = 1
attempt = 0    
while missing != 0  and attempt < max_attempts:
    time.sleep(3)
    missing = 1 - download(
        bbox_tassello,
        execution['outputpath'],
        custom_names,
        custom_csvs,
        poi_category_osm,
        aoi.get('mode') or 'walk',
        aoi.get('weight') or 'time',
        park.get('park_gates_source') or 'osm',
        park.get('park_gates_osm_buffer_m') or 10,
        park.get('park_gates_csv_path') or None,
        park.get('park_gates_virtual_distance_m') or 100
        )
    attempt += 1


print_end("DOWNLOAD", t0_download, t_start_download)

# ---------------------------------------------------------------------------------
# COMPUTO
# ---------------------------------------------------------------------------------
t0_computo = print_start("COMPUTO")
t_start_computo = datetime.now()


result_computo = computo(
    bbox_tassello,
    tile.at[0, 'latitude'],
    tile.at[0, 'longitude'],
    tile.at[0, 'radius'],
    execution['outputpath'],
    custom_names,
    custom_csvs,
    grid.get('grid_path'),
    poi_category_osm,  
    aoi.get('clip_layer_path'),
    aoi.get('name'),
    aoi.get('bike_speed_kmh') or 15,
    aoi.get('walk_speed_kmh') or 5,
    aoi.get('mode')  or 'walk',
    aoi.get('weight') or 'time'
    
)


print('----------------------------------------------------------------------------------------------------------------', flush=True)
print("COMPUTO end.\n", flush=True)


print_end("COMPUTO", t0_computo, t_start_computo)

# ---------------- SCRIPT END ----------------
script_end_time = datetime.now()
dt = (script_end_time - script_start_time).total_seconds()

print()
print(f"[{ts()}] SCRIPT ENDS (Durata: {dt:.2f}s = {dt/60:.2f}m = {dt/3600:.2f}h)", flush=True)
print("=============================================================================================", flush=True)
