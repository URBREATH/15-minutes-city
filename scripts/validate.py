import sys
import os
import time
from datetime import datetime
import pandas as pd
import json
import warnings
import traceback
from pyproj import CRS
from pyproj.exceptions import CRSError
from scripts.errors import raise_error
from scripts.parameters import read_param, section_exists_and_has_fields
import logging
from logging.handlers import RotatingFileHandler
from scripts.logger import logger
from scripts.storage_minio import check_path_exists,split_path,get_s3_client,minio_file_exists,minio_copy_prefix,minio_list_poi_categories,is_minio_path,split_bucket_and_prefix,load_pois_from_minio

def validate_api_params(params: dict):


    # -------------------
    # Execution
    # -------------------
    execution = params.get("execution", {})
    aoi = params.get("aoi", {})
    poi = params.get("poi", {})
    park = params.get("park", {})
    grid = params.get("grid", {})

    missing_fields = []

    if not aoi or "bbox" not in aoi:
        missing_fields.append("aoi_bbox")

    if not execution.get("filename"):
        missing_fields.append("execution_filename")

    if not execution.get("output_local_path"):
        missing_fields.append("execution_output_local_path")

    if execution.get("output_minio_path") and not execution.get("output_local_path"):
        missing_fields.append("execution_output_local_path_required_with_minio")

    if missing_fields:
        raise_error("ERR_002", extra=" | ".join(missing_fields))

    # MinIO keys check
    if execution.get("output_minio_path"):
        access_key = os.getenv("MINIO_ACCESS_KEY")
        secret_key = os.getenv("MINIO_SECRET_KEY")
        endpoint_url = os.getenv("MINIO_ENDPOINT_URL")
        if not access_key or not secret_key or not endpoint_url:
            raise_error("ERR_004")
    
    # ENUM validation
    weight = execution.get("weight") or "time"
    if weight not in ["time", "distance"]:
        raise_error("ERR_005", extra="time | distance")

    mode = execution.get("mode") or "walk"
    if mode not in ["walk", "bike"]:
        raise_error("ERR_006", extra="walk | bike")

    # -------------------
    # POI
    # -------------------
    poi_category_osm = poi.get("poi_category_osm")
    poi_category_custom_name = poi.get("poi_category_custom_name")
    poi_category_custom_csv = poi.get("poi_category_custom_csv")
    poi_category_custom_style = poi.get("poi_category_custom_style")

    with open("./config/poi_category_osm_tag.json", "r", encoding="utf-8") as f:
        osm_tags = json.load(f)

    valid_poi_category_osm = set(osm_tags.keys()) | {"all"}

    if poi_category_osm and poi_category_osm not in valid_poi_category_osm:
        raise_error("ERR_007", extra=f"{'| '.join(valid_poi_category_osm)}")

    # Validate custom POI
    custom_names = ["".join(x.lower().split()) for x in poi_category_custom_name.split(",")] if poi_category_custom_name else []
    custom_csvs = [x.strip() for x in poi_category_custom_csv.split(",")] if poi_category_custom_csv else []
    custom_styles = [x.strip() for x in poi_category_custom_style.split(",")] if poi_category_custom_style else []

    conflicting_custom = [name for name in custom_names if name in valid_poi_category_osm]
    if conflicting_custom:
        raise_error("ERR_008", extra="custom category cannot match OSM category")

    if custom_names or custom_csvs:
        if len(custom_names) != len(custom_csvs):
            raise_error("ERR_009", extra="custom categories count must match CSV categories count")

    # STYLE CONTROLS
    
    if custom_styles:
        if not custom_csvs:
            raise_error("ERR_010")
    
        if len(custom_styles) > len(custom_csvs):
            raise_error("ERR_011")
    
        for s in custom_styles:
            if is_minio_path(s):
                check_path_exists(s, "ERR_012", endpoint_url, access_key, secret_key)
            else:
                if not os.path.isfile(s):
                    raise_error("ERR_012", extra=s)
    

    # -------------------
    # PARK
    # -------------------
    park_source = park.get("park_gates_source") or "osm"
    valid_park_source = ["osm", "csv", "road_intersect", "virtual"]
    if park_source not in valid_park_source:
        raise_error("ERR_013", extra=f"{'| '.join(valid_park_source)}")

    park_csv = (park.get("park_gates_csv") or "").strip()
    
    if park_source == "csv":
        if not park_csv:
            raise_error("ERR_014", extra=park_csv)
    
        if is_minio_path(park_csv):
            check_path_exists(park_csv, "ERR_014", endpoint_url, access_key, secret_key)
        else:
            if not os.path.isfile(park_csv):
                raise_error("ERR_014", extra=park_csv)


    # CSV existence check
    if custom_names or custom_csvs:
        for f in custom_csvs:
            if is_minio_path(f):
                check_path_exists(f, "ERR_015", endpoint_url, access_key, secret_key)
            else:
                if not os.path.exists(f):
                    raise_error("ERR_015", extra=f)

    # -------------------
    # GRID
    # -------------------
    clip_layer = grid.get("clip_layer")
    
    
    if clip_layer:
        if is_minio_path(clip_layer):            
            check_path_exists(clip_layer, "ERR_016", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(clip_layer):
                raise_error("ERR_016", extra=clip_layer)

    grid_gpkg = grid.get("grid_gpkg")
    
    if grid_gpkg:
        if is_minio_path(grid_gpkg):
            check_path_exists(grid_gpkg, "ERR_017", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(grid_gpkg):
                raise_error("ERR_017", extra=grid_gpkg)

    
    output_format = execution.get('output_format') or 'gpkg'
    output_epsg = execution.get('output_epsg') or '3857'
    if output_format not in ["csv", "gpkg", "geojson"]:
        raise_error("ERR_018", extra= "csv | gpkg | geojson")
    
    
    try:
        CRS.from_epsg(int(output_epsg))
    except (CRSError, ValueError, TypeError):
        raise_error(
            "ERR_019",
            extra="must be a valid EPSG code (e.g., 3857, 4326, 32632)"
        )

        
    return params
    
    
# ------------------------------------------------
# PARAMETERS VALIDATION
# ------------------------------------------------
def validate_parameters(parameters_file):

    aoi_parameters = read_param(parameters_file, 'aoi')
    execution_parameters = read_param(parameters_file, 'execution')

    required_aoi = ['bbox']
    required_execution = ['filename']

    missing_fields = []

    if not section_exists_and_has_fields(parameters_file, 'aoi', required_aoi):
        missing_fields.append("aoi_bbox")

    if not section_exists_and_has_fields(parameters_file, 'execution', required_execution):
        missing_fields.append("execution_filename")

    local_path = execution_parameters.get('output_local_path')
    minio_path = execution_parameters.get('output_minio_path')

    if not local_path:
        missing_fields.append("execution_output_local_path")

    if minio_path and not local_path:
        missing_fields.append("execution_output_local_path_required_with_minio")

    if missing_fields:
        raise_error(
            "ERR_002",
            extra="aoi_bbox | execution_filename | execution_output_local_path"
        )

    if execution_parameters.get('output_minio_path'):
        access_key = os.getenv("MINIO_ACCESS_KEY")
        secret_key = os.getenv("MINIO_SECRET_KEY")
        endpoint_url = os.getenv("MINIO_ENDPOINT_URL")  
        
        if not access_key or not secret_key or not endpoint_url:        
            raise_error(
                "ERR_004"
                )
    weight = execution_parameters.get('weight') or 'time'
    if weight not in ["time", "distance"]:
        raise_error("ERR_005", extra="time | distance")

    mode = execution_parameters.get('mode') or 'walk'
    if mode not in ["walk", "bike"]:
        raise_error("ERR_006", extra="walk | bike")

    try:
        poi_parameters = read_param(parameters_file, 'poi')
    except:
        poi_parameters = {}
    poi_category_osm = poi_parameters.get('poi_category_osm') 
    poi_category_custom_name = poi_parameters.get('poi_category_custom_name')
    poi_category_custom_csv = poi_parameters.get('poi_category_custom_csv')
    poi_category_custom_style = poi_parameters.get('poi_category_custom_style')

    with open("./config/poi_category_osm_tag.json", "r", encoding="utf-8") as f:
        osm_tags = json.load(f)
            
    # Valid OSM categories
    valid_poi_category_osm = set(osm_tags.keys()) | {"all"}
    
    if poi_category_osm and poi_category_osm not in valid_poi_category_osm:
        raise_error(
            "ERR_007",
            extra=f"{'| '.join(valid_poi_category_osm)}"
        )
    # Validate custom POI
    custom_names = ["".join(x.lower().split()) for x in poi_category_custom_name.split(",")] if poi_category_custom_name else []
    custom_csvs = [x.strip() for x in poi_category_custom_csv.split(",")] if poi_category_custom_csv else []
    custom_styles = [x.strip() for x in poi_category_custom_style.split(",")] if poi_category_custom_style else []


    conflicting_custom = [name for name in custom_names if name in valid_poi_category_osm]
    if conflicting_custom:
        raise_error(
            "ERR_008",
            extra="custom category cannot match OSM category"
        )
    
    if custom_names or custom_csvs:
        if len(custom_names) != len(custom_csvs):
            raise_error("ERR_009", extra ="custom categories count must match CSV categories count")

    # --- STYLE CONTROLS ---
    
    if custom_styles:
        if not custom_csvs:
            raise_error("ERR_010")
    
        if len(custom_styles) > len(custom_csvs):
            raise_error("ERR_011")
    
        for s in custom_styles:
            if is_minio_path(s):
                check_path_exists(s, "ERR_012", endpoint_url, access_key, secret_key)
            else:
                if not os.path.isfile(s):
                    raise_error("ERR_012", extra=s)
    
                
       
    # ---------------- PARK ----------------                                                                             

    try:
        park_parameters = read_param(parameters_file, 'park')
    except:
        park_parameters = {}
    park_source = park_parameters.get('park_gates_source') or 'osm'
    valid_park_source = ["osm", "csv", "road_intersect", "virtual"]
    if park_source not in valid_park_source:
        raise_error("ERR_013", extra=f"{'| '.join(valid_park_source)}")


    park_csv = park_parameters.get('park_gates_csv', '').strip()

    if park_source == "csv":
        if not park_csv:
            raise_error("ERR_014", extra=park_csv)
    
        if is_minio_path(park_csv):
            check_path_exists(park_csv, "ERR_014", endpoint_url, access_key, secret_key)
        else:
            if not os.path.isfile(park_csv):
                raise_error("ERR_014", extra=park_csv)

    # CSV existence check
    if custom_names or custom_csvs:
        for f in custom_csvs:
            if is_minio_path(f):
                check_path_exists(f, "ERR_015", endpoint_url, access_key, secret_key)
            else:
                if not os.path.exists(f):
                    raise_error("ERR_015", extra=f)

    try:
        grid_parameters = read_param(parameters_file, 'grid')
    except:
        grid_parameters = {}

    clip_layer = grid_parameters.get('clip_layer')

    if clip_layer:
        if is_minio_path(clip_layer):
            check_path_exists(clip_layer, "ERR_016", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(clip_layer):
                raise_error("ERR_016", extra=clip_layer)        
    grid_gpkg = grid_parameters.get('grid_gpkg')
    if grid_gpkg:
        if is_minio_path(grid_gpkg):
            check_path_exists(grid_gpkg, "ERR_017", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(grid_gpkg):
                raise_error("ERR_017", extra=grid_gpkg)                                                
    
    output_format = execution_parameters.get('output_format') or 'gpkg'
    output_epsg = execution_parameters.get('output_epsg') or '3857'
    if output_format not in ["csv", "gpkg", "geojson"]:
        raise_error("ERR_018", extra= "csv | gpkg | geojson")
   
    
    try:
        CRS.from_epsg(int(output_epsg))
    except (CRSError, ValueError, TypeError):
        raise_error(
            "ERR_019",
            extra="must be a valid EPSG code (e.g., 3857, 4326, 32632)"
        )


    return {
        "aoi": aoi_parameters,
        "poi": poi_parameters,
        "park": park_parameters,
        "grid": grid_parameters,
        "execution": execution_parameters
    }
