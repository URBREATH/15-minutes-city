import sys
import os
import time
from datetime import datetime
import pandas as pd
import json
import warnings
import traceback
import shutil
from scripts.errors import raise_error
from scripts.index_processing import create_bbox, download, computo
from scripts.parameters import read_param, section_exists_and_has_fields
import logging
from logging.handlers import RotatingFileHandler
from scripts.logger import logger
from scripts.validate import validate_parameters
from scripts.storage_minio import (
    check_folder_exists,
    is_minio_path,
    split_path, get_s3_client
)

from io import BytesIO

warnings.filterwarnings("ignore")


default_mode = 'walk'
default_weight =  'time'
default_bike_speed_kmh = 15.0
default_walk_speed_kmh = 5.0
default_output_format ='gpkg'
default_output_epsg = 3857
default_network_edges = ''
default_network_nodes =''
default_poi_osm_path =  ''
default_park_gates_source = 'osm'
default_park_gates_osm_buffer_m = 10.0
default_park_gates_csv = None
default_park_gates_virtual_distance_m = 100.0
default_hex_diameter_m = 250.0
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
    network = params["network"]
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
   
    
    mode = execution.get('mode') or default_mode
    weight = execution.get('weight') or default_weight
    bike_speed_kmh = execution.get('bike_speed_kmh') or default_bike_speed_kmh
    walk_speed_kmh = execution.get('walk_speed_kmh') or default_walk_speed_kmh
    output_format = execution.get('output_format') or default_output_format
    output_epsg = execution.get('output_epsg') or default_output_epsg
    network_edges = network.get('network_edges') or default_network_edges
    network_nodes = network.get('network_nodes') or default_network_nodes
    poi_osm_path = poi.get('poi_osm_path') or default_poi_osm_path
    park_gates_source = park.get('park_gates_source') or default_park_gates_source
    park_gates_osm_buffer_m = park.get('park_gates_osm_buffer_m') or default_park_gates_osm_buffer_m 
    park_gates_csv = park.get('park_gates_csv') or default_park_gates_csv
    park_gates_virtual_distance_m = park.get('park_gates_virtual_distance_m') or default_park_gates_virtual_distance_m
    hex_diameter_m = grid.get('hex_diameter_m') or default_hex_diameter_m
    output_local_path = execution.get('output_local_path')
    grid_gpkg = grid.get('grid_gpkg')
    clip_layer = grid.get('clip_layer')
    virtual_nodes = grid.get("virtual_nodes", "false").strip().lower() == "true"
    filename = execution.get('filename')
    poi_category_custom_style = execution.get('poi_category_custom_style')
    
    effective_params = {
        "bbox": aoi['bbox'],
        "output_local_path": output_local_path,
        "output_minio_path": new_path_output_minio_path,  
        "filename": filename, 
        "mode": mode,
        "weight": weight,
    
        "bike_speed_kmh": bike_speed_kmh,
        "walk_speed_kmh": walk_speed_kmh,

        "output_format": output_format,
        "output_epsg": output_epsg,
        
        "network_edges": network_edges,
        "network_nodes": network_nodes,
        "poi_osm_path": poi_osm_path ,
        "poi_category_osm": poi_category_osm,
        "custom_names": custom_names,
        "custom_csvs": custom_csvs,
    
        "park_gates_source": park_gates_source,
        "park_gates_osm_buffer_m": park_gates_osm_buffer_m,
        "park_gates_csv": park_gates_csv,
        "park_gates_virtual_distance_m": park_gates_virtual_distance_m,
        
        "grid_gpkg": grid_gpkg,
        "hex_diameter_m":hex_diameter_m ,
        "clip_layer": clip_layer,
        "virtual_nodes": virtual_nodes
    }
    
    logger.info("\n================ PARAMETERS USED ================\n")
    
    for k, v in effective_params.items():
        logger.info(f"{k:35} : {v}")
    
    logger.info("\n=================================================\n") 

    # ------------------------------------------------
    # CREATE BBOX
    # ------------------------------------------------
    
    
    for sub in ["grid", "osm_network", "osm_poi", "custom_poi", "output", "style"]:
        shutil.rmtree(os.path.join(output_local_path, sub), ignore_errors=True)

    create_bbox(
        bbox,
        output_local_path,
        new_path_output_minio_path,
        float(hex_diameter_m),
        access_key,
        secret_key,
        endpoint_url
    )

    

    if output_local_path:
        if is_minio_path(output_local_path):
            
            check_folder_exists(output_local_path, "ERR_003", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(output_local_path):
                raise_error("ERR_003", extra=output_local_path)
    

    # ------------------------------------------------
    # DOWNLOAD
    # ------------------------------------------------
    t0_download = print_start("DOWNLOAD")

    grid_ref_path = execution.get('output_local_path')
    if is_minio_path(grid_ref_path):
        
        bucket, prefix = split_path(grid_ref_path)
        key = f"{prefix.rstrip('/')}/grid/grid_parameter.csv"
    
        s3 = get_s3_client(access_key, secret_key, endpoint_url)
        obj = s3.get_object(Bucket=bucket, Key=key)
    
        tile = pd.read_csv(
            BytesIO(obj["Body"].read()),
            sep=';',
            header=0
        )
    else:
        grid_folder = os.path.join(grid_ref_path, "grid")
        bbox_file = os.path.join(grid_folder, "grid_parameter.csv")
        tile = pd.read_csv(bbox_file, sep=';', header=0)


    aoi_bbox = tile.at[0, 'downloadBBox']

    download(
        aoi_bbox,
        output_local_path,
        custom_names,
        custom_csvs,
        poi_category_osm,
        access_key,
        secret_key,
        endpoint_url,        
        new_path_output_minio_path,
        network_edges,
        network_nodes,
        poi_osm_path,        
        mode,
        weight,
        park_gates_source,
        park_gates_osm_buffer_m,
        park_gates_csv,
        park_gates_virtual_distance_m
    )

    print_end("DOWNLOAD", t0_download)

    # ------------------------------------------------
    # EXECUTION
    # ------------------------------------------------
    t0_computo = print_start("EXECUTION")

        
    computo(
        aoi_bbox,
        tile.at[0, 'latitude'],
        tile.at[0, 'longitude'],
        tile.at[0, 'hex_radius_m'],
        output_local_path,
        custom_names,
        custom_csvs,
        grid_gpkg,
        poi_category_osm,
        clip_layer,
        filename,
        access_key,
        secret_key,
        endpoint_url,
        poi_category_custom_style,
        new_path_output_minio_path,
        virtual_nodes,
        output_format,
        output_epsg,
        bike_speed_kmh,
        walk_speed_kmh,
        mode,
        weight
    )

    print_end("EXECUTION", t0_computo)

    script_end_time = datetime.now()
    dt = (script_end_time - script_start_time).total_seconds()

    logger.info("")
    logger.info(f"[{ts()}] SCRIPT ENDS ( {dt:.2f}s = {dt/60:.2f}m = {dt/3600:.2f}h)")
    logger.info("=============================================================================================")
    if new_path_output_minio_path:
   
        result_path = f"s3://{new_path_output_minio_path}/output/{filename}.{output_format}"
    else:
    # CLI 
        result_path = os.path.join(
            output_local_path,
            "output",
            f"{filename}.{output_format}"
        )
    return {
        "result_path": result_path
    }



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
