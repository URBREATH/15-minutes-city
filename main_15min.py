import sys
import os
import time
from datetime import datetime
import pandas as pd
import json
import warnings
import traceback

from scripts.errors import raise_error
from scripts.index_processing import create_bbox, download, computo
from scripts.parameters import read_param, section_exists_and_has_fields
import logging
from logging.handlers import RotatingFileHandler
from scripts.logger import logger
from scripts.validate import validate_parameters

warnings.filterwarnings("ignore")

# ------------------------------------------------
# UTILITY FUNCTIONS
# ------------------------------------------------
def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def print_start(msg):
    logger.info(f"[{ts()}] {msg}") 
    logger.info("---------------------------------------------------------------------------------------------")
    return time.time()


def print_end(msg, t0):
    dt = time.time() - t0
    logger.info("---------------------------------------------------------------------------------------------") 
    logger.info(
        f"[{ts()}] END {msg} "
        f"( {dt:.2f}s = {dt/60:.2f}m = {dt/3600:.2f}h) ")
    
    return dt


# ------------------------------------------------
# CORE ANALYSIS
# ------------------------------------------------
def run_analysis(params: dict):

    script_start_time = datetime.now()

    aoi = params["aoi"]
    grid = params["grid"]
    execution = params["execution"]
    poi = params["poi"]
    park = params["park"]

    # --- MinIO ---
    if execution.get('output_minio_path'):
        access_key = os.getenv("MINIO_ACCESS_KEY")
        secret_key = os.getenv("MINIO_SECRET_KEY")
        endpoint_url = os.getenv("MINIO_ENDPOINT_URL")

        folder, name = execution.get('output_minio_path').rsplit("/", 1)
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        new_path_output_minio_path = f"{folder}/{timestamp}_{name}"
    else:
        access_key = None
        secret_key = None
        endpoint_url = None
        new_path_output_minio_path = None

    # --- POI ---
    poi_category_custom_name = poi.get('poi_category_custom_name')
    poi_category_custom_csv = poi.get('poi_category_custom_csv')

    custom_names = ["".join(x.lower().split()) for x in poi_category_custom_name.split(",")] if poi_category_custom_name else []
    custom_csvs = [x.strip() for x in poi_category_custom_csv.split(",")] if poi_category_custom_csv else []


    poi_category_osm = poi.get('poi_category_osm') or ('all' if not poi.get('poi_category_custom_name') else None)

    bbox = aoi['bbox']

    if isinstance(bbox, str):
        # stringa → da CLI / INI
        bbox = eval(bbox)
    else:
        # già lista → da API
        bbox = bbox


    effective_params = {
        "bbox": aoi['bbox'],
        "output_local_path": execution.get('output_local_path'),
        "output_minio_path": new_path_output_minio_path,  
    
        "mode": execution.get('mode') or 'walk',
        "weight": execution.get('weight') or 'time',
    
        "bike_speed_kmh": execution.get('bike_speed_kmh') or 15.0,
        "walk_speed_kmh": execution.get('walk_speed_kmh') or 5.0,
    
        "poi_category_osm": poi_category_osm,
        "custom_names": custom_names,
        "custom_csvs": custom_csvs,
    
        "park_gates_source": park.get('park_gates_source') or 'osm',
        "park_gates_osm_buffer_m": park.get('park_gates_osm_buffer_m') or 10.0,
        "park_gates_csv": park.get('park_gates_csv') or None,
        "park_virtual_distance_m": park.get('park_gates_virtual_distance_m') or 100.0,
        
        "grid_gpkg":  grid.get('grid_gpkg'),
        "hex_diameter_m": grid.get('hex_diameter_m') or 250.0,
        "clip_layer": grid.get('clip_layer'),
        "virtual_nodes": grid.get("virtual_nodes", "false").strip().lower() == "true"
    }
    
    logger.info("\n================ PARAMETERS USED ================\n")
    
    for k, v in effective_params.items():
        logger.info(f"{k:35} : {v}")
    
    logger.info("\n=================================================\n") 

    # ------------------------------------------------
    # CREATE BBOX
    # ------------------------------------------------
    create_bbox(
        bbox,
        execution.get('output_local_path'),
        new_path_output_minio_path,
        float(grid.get('hex_diameter_m') or 250.0),
        access_key,
        secret_key,
        endpoint_url
    )

    if not os.path.exists(execution.get('output_local_path')):
        raise_error("ERR_003")

    # ------------------------------------------------
    # DOWNLOAD
    # ------------------------------------------------
    t0_download = print_start("DOWNLOAD")

    grid_folder = os.path.join(execution.get('output_local_path'), "grid")
    bbox_file = os.path.join(grid_folder, "grid_parameter.csv")
    tile = pd.read_csv(bbox_file, sep=';', header=0)

    bbox_tassello = tile.at[0, 'downloadBBox']

    download(
        bbox_tassello,
        execution.get('output_local_path'),
        custom_names,
        custom_csvs,
        poi_category_osm,
        access_key,
        secret_key,
        endpoint_url,
        new_path_output_minio_path,
        execution.get('mode') or 'walk',
        execution.get('weight') or 'time',
        park.get('park_gates_source') or 'osm',
        park.get('park_gates_osm_buffer_m') or 10.0,
        park.get('park_gates_csv') or None,
        park.get('park_gates_virtual_distance_m') or 100.0
    )

    print_end("DOWNLOAD", t0_download)

    # ------------------------------------------------
    # EXECUTION
    # ------------------------------------------------
    t0_computo = print_start("EXECUTION")

    computo(
        bbox_tassello,
        tile.at[0, 'latitude'],
        tile.at[0, 'longitude'],
        tile.at[0, 'hex_radius_m'],
        execution.get('output_local_path'),
        custom_names,
        custom_csvs,
        grid.get('grid_gpkg'),
        poi_category_osm,
        grid.get('clip_layer'),
        execution.get('filename'),
        access_key,
        secret_key,
        endpoint_url,
        execution.get('poi_category_custom_style'),
        new_path_output_minio_path,
        grid.get("virtual_nodes", "false").strip().lower() == "true",
        execution.get('bike_speed_kmh') or 15.0,
        execution.get('walk_speed_kmh') or 5.0,
        execution.get('mode') or 'walk',
        execution.get('weight') or 'time'
    )

    print_end("EXECUTION", t0_computo)

    script_end_time = datetime.now()
    dt = (script_end_time - script_start_time).total_seconds()

    logger.info("")
    logger.info(f"[{ts()}] SCRIPT ENDS ( {dt:.2f}s = {dt/60:.2f}m = {dt/3600:.2f}h)")
    logger.info("=============================================================================================")



if __name__ == '__main__':

    try:
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

        
        # Ora tutto il resto dello script
        logger.info("=============================================================================================")
        logger.info(f"[{ts()}] SCRIPT STARTS\n")
        

        params = validate_parameters(parameters_file)

        run_analysis(params)

    except Exception as e:
        logger.error("ERROR: Script execution failed")
        logger.error(str(e))
        logger.error(traceback.format_exc())
        print("ERROR:", e)
        sys.exit(1)
