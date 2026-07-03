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
from scripts.storage_minio import sync_minio, split_path
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
default_virtual_nodes = "false"
default_poi_category_custom_name = 'all'
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


    poi_category_osm = poi.get('poi_category_osm') or (default_poi_category_custom_name if not poi.get('poi_category_custom_name') else None)


    poi_category_complementary_name = poi.get('poi_category_complementary_name')
    poi_category_complementary_csv =poi.get('poi_category_complementary_csv')
    poi_category_complementary_style =poi.get('poi_category_complementary_style')

    complementary_names = ["".join(x.lower().split()) for x in poi_category_complementary_name.split(",")] if poi_category_complementary_name else []
    complementary_csvs = [x.strip() for x in poi_category_complementary_csv.split(",")] if poi_category_complementary_csv else []
    
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
    virtual_nodes = grid.get("virtual_nodes", default_virtual_nodes).strip().lower() == "true"
    filename = execution.get('filename')
    poi_category_custom_style = poi.get('poi_category_custom_style')
    
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
        "custom_styles": poi_category_custom_style,
        "complementary_names":complementary_names,
        "complementary_csvs": complementary_csvs,
        "complementary_styles": poi_category_complementary_style,
    
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
    
    
    for sub in ["grid", "osm_network", "osm_poi", "custom_poi", "complementary_poi" ,"output", "style"]:
        shutil.rmtree(os.path.join(output_local_path, sub), ignore_errors=True)

    
    grid_folder = create_bbox(bbox, output_local_path, float(hex_diameter_m))
    
    # upload finale
    sync_minio(
        "upload",
        grid_folder,
        new_path_output_minio_path,
        access_key, secret_key, endpoint_url,
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
    # 1. leggi il grid_parameter.csv
    bbox_file = os.path.join(output_local_path, "grid", "grid_parameter.csv")
    tile = pd.read_csv(bbox_file, sep=';', header=0)
    aoi_bbox = tile.at[0, 'downloadBBox']
    #_staging è una cartella temporanea di lavoro dove vengono "parcheggiati" i file scaricati da MinIO prima di essere usati dallo script.
    stage_dir = os.path.join(output_local_path, "_staging")
    # _ per gli input network_edgesedges_in.csvArchi del grafo stradale (input rete)
    # --- NETWORK EDGES ---
    network_edges_local = network_edges
    if network_edges and is_minio_path(network_edges):
        network_edges_local = os.path.join(stage_dir, "edges_in.csv")
        sync_minio("download", network_edges_local, network_edges,
                   access_key, secret_key, endpoint_url)
    
    # --- NETWORK NODES ---
    network_nodes_local = network_nodes
    if network_nodes and is_minio_path(network_nodes):
        network_nodes_local = os.path.join(stage_dir, "nodes_in.csv")
        sync_minio("download", network_nodes_local, network_nodes,
                   access_key, secret_key, endpoint_url)
    
    # --- POI OSM PATH ---
    poi_osm_path_local = poi_osm_path
    if poi_osm_path and is_minio_path(poi_osm_path):
        poi_osm_path_local = os.path.join(stage_dir, "poi_osm_in")
        sync_minio("download", poi_osm_path_local, poi_osm_path,
                   access_key, secret_key, endpoint_url)
    
    # --- PARK GATES CSV ---
    park_gates_csv_local = park_gates_csv
    if park_gates_csv and is_minio_path(park_gates_csv):
        park_gates_csv_local = os.path.join(stage_dir, "park_gates.csv")
        sync_minio("download", park_gates_csv_local, park_gates_csv,
                   access_key, secret_key, endpoint_url)
    
    # --- CUSTOM CSVs ---
    # Indice i nel nome → custom_0.csv, custom_1.csv, ecc., perché possono essercene N e ti serve un nome univoco.
    custom_csvs_local = []
    for i, p in enumerate(custom_csvs or []):
        if p and is_minio_path(p):
            local_p = os.path.join(stage_dir, f"custom_{i}.csv")
            sync_minio("download", local_p, p,
                       access_key, secret_key, endpoint_url)
            custom_csvs_local.append(local_p)
        else:
            custom_csvs_local.append(p)
    
    # --- COMPLEMENTARY CSVs ---
    complementary_csvs_local = []
    for i, p in enumerate(complementary_csvs or []):
        if p and is_minio_path(p):
            local_p = os.path.join(stage_dir, f"complementary_{i}.csv")
            sync_minio("download", local_p, p,
                       access_key, secret_key, endpoint_url)
            complementary_csvs_local.append(local_p)
        else:
            complementary_csvs_local.append(p)
    
    # 3. CORE: download senza parametri MinIO
    download(
        aoi_bbox,
        output_local_path,
        custom_names,
        custom_csvs_local,
        poi_category_osm,
        complementary_names,
        complementary_csvs_local,         
        network_edges_local,
        network_nodes_local,
        poi_osm_path_local,
        mode,
        weight,
        park_gates_source,
        park_gates_osm_buffer_m,
        park_gates_csv_local,
        park_gates_virtual_distance_m,
    )
    
    # 4. UPLOAD finale di tutto ciò che ha prodotto il download
    if new_path_output_minio_path:
        for sub in ["osm_network", "osm_poi", "custom_poi"]:
            sync_minio(
                "upload",
                os.path.join(output_local_path, sub),
                new_path_output_minio_path,
                access_key, secret_key, endpoint_url,
            )
    
    print_end("DOWNLOAD", t0_download)
    # ------------------------------------------------
    # EXECUTION
    # ------------------------------------------------
    t0_computo = print_start("EXECUTION")
    
    # staging input opzionali
    grid_gpkg_local = grid_gpkg
    if grid_gpkg and is_minio_path(grid_gpkg):
        grid_gpkg_local = os.path.join(stage_dir, "grid_in.gpkg")
        sync_minio("download", grid_gpkg_local, grid_gpkg,
                   access_key, secret_key, endpoint_url)
    
    clip_layer_local = clip_layer
    if clip_layer and is_minio_path(clip_layer):
        clip_layer_local = os.path.join(stage_dir, "clip_in.gpkg")
        sync_minio("download", clip_layer_local, clip_layer,
                   access_key, secret_key, endpoint_url)
    
    computo(
        aoi_bbox,
        tile.at[0, 'latitude'],
        tile.at[0, 'longitude'],
        tile.at[0, 'hex_radius_m'],
        output_local_path,
        custom_names,
        custom_csvs_local,
        grid_gpkg_local,
        poi_category_osm,
        clip_layer_local,
        filename,
        complementary_names,
        complementary_csvs_local,
        poi_category_custom_style,
        poi_category_complementary_style,
        new_path_output_minio_path,
        virtual_nodes,
        output_format,
        output_epsg,
        bike_speed_kmh,
        walk_speed_kmh,
        mode,
        weight
    )

    if new_path_output_minio_path:
        # 1) output e grid
        for sub in ["output", "grid"]:
            local_sub = os.path.join(output_local_path, sub)
            if os.path.isdir(local_sub):
                sync_minio(
                    "upload",
                    local_sub,
                    new_path_output_minio_path,
                    access_key, secret_key, endpoint_url,
                )
    
    # 2) style: integrare SLD OSM di default DENTRO output_local_path/style
    #    (in cui computo() ha già messo gli SLD custom/complementary)
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    default_style_dir = os.path.join(SCRIPT_DIR, "style")  
    
    style_dir = os.path.join(output_local_path, "style")
    os.makedirs(style_dir, exist_ok=True)
    
    # Categorie OSM attive in questo run
    if poi_category_osm and poi_category_osm.lower() != "all":
        active_osm = [c.strip() for c in poi_category_osm.split(",") if c.strip()]
    else:
        # "all" → copio tutto ciò che trovo in default_style_dir
        active_osm = None
    
    if os.path.isdir(default_style_dir):
        for fname in os.listdir(default_style_dir):
            src = os.path.join(default_style_dir, fname)
            if not os.path.isfile(src):
                continue
    
            base, ext = os.path.splitext(fname)
            if ext.lower() != ".sld":
                continue
    
            # Filtra: porto solo SLD per categorie OSM attive
            # (oltre a overall_average / overall_max che servono sempre)
            if active_osm is not None and base not in active_osm and base not in ("overall_average", "overall_max"):
                continue
    
            dst = os.path.join(style_dir, fname)
            if os.path.exists(dst):
                # già presente (es. messo da computo per custom/complementary) → non sovrascrivere
                logger.info(f"[style merge] keep existing: {dst}")
                continue
    
            try:
                shutil.copy2(src, dst)
                logger.info(f"[style merge] copied: {src} → {dst}")
            except PermissionError:
                shutil.copyfile(src, dst)
                logger.info(f"[style merge] copied (no metadata): {src} → {dst}")
    
    # 3) upload style su MinIO
    if os.path.isdir(style_dir) and os.listdir(style_dir):
        sync_minio(
            "upload",
            style_dir,
            new_path_output_minio_path,
            access_key, secret_key, endpoint_url,
        )


    if complementary_names and new_path_output_minio_path:

        sync_minio(
            "upload",
            os.path.join(output_local_path, "complementary_poi"),
            new_path_output_minio_path,
            access_key, secret_key, endpoint_url,
        )
            
    print_end("EXECUTION", t0_computo)

    shutil.rmtree(stage_dir, ignore_errors=True)

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
