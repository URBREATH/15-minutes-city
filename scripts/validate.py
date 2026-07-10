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
from scripts.storage_minio import is_minio_path,check_path_exists,check_folder_exists

def validate_api_params(params: dict):

    # -------------------
    # Execution
    # -------------------
    execution = params.get("execution", {})
    aoi = params.get("aoi", {})
    network = params.get("network", {})
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
    else:
        access_key = None
        secret_key = None
        endpoint_url = None

    # ENUM validation
    weight = execution.get("weight")
    if weight:
        if weight not in ["time", "distance"]:
            raise_error("ERR_005", extra="time | distance")

    mode = execution.get("mode")
    if mode:
        if mode not in ["walk", "bike"]:
            raise_error("ERR_006", extra="walk | bike")

    # -------------------
    # NETWORK
    # -------------------
    network_nodes = network.get("network_nodes")

    if network_nodes:
        if is_minio_path(network_nodes):
            check_path_exists(
                network_nodes,
                "ERR_010",
                endpoint_url,
                access_key,
                secret_key
            )
        else:
            if not os.path.isfile(network_nodes):
                raise_error("ERR_010", extra=network_nodes)

    network_edges = network.get("network_edges")

    if network_edges:
        if is_minio_path(network_edges):
            check_path_exists(
                network_edges,
                "ERR_011",
                endpoint_url,
                access_key,
                secret_key
            )
        else:
            if not os.path.isfile(network_edges):
                raise_error("ERR_011", extra=network_edges)

    if (network_nodes and not network_edges) or (network_edges and not network_nodes):
        raise_error("ERR_012")

    # -------------------
    # POI
    # -------------------
    poi_category_osm = poi.get("poi_category_osm")
    poi_category_custom_name = poi.get("poi_category_custom_name")
    poi_category_custom_csv = poi.get("poi_category_custom_csv")
    poi_category_custom_style = poi.get("poi_category_custom_style")

    poi_category_extended_name = poi.get("poi_category_extended_name")
    poi_category_extended_csv = poi.get("poi_category_extended_csv")
    poi_category_extended_style = poi.get("poi_category_extended_style")

    with open("./config/poi_category_osm_tag.json", "r", encoding="utf-8") as f:
        osm_tags = json.load(f)

    valid_poi_category_osm = set(osm_tags.keys()) | {"all"}
    has_osm = bool(poi_category_osm and poi_category_osm.strip())
    has_custom = bool(poi_category_custom_name and poi_category_custom_name.strip())

    if has_osm:

        if poi_category_osm.lower().strip() == "all":
            poi_category_osm_list = valid_poi_category_osm.copy()

        else:
            poi_category_osm_list = [
                c.strip().lower()
                for c in poi_category_osm.split(",")
                if c.strip()
            ]

            invalid_categories = [
                c for c in poi_category_osm_list
                if c not in valid_poi_category_osm
            ]

            if invalid_categories:
                raise_error(
                    "ERR_013",
                    extra=(
                        f"Invalid POI category(ies): {', '.join(invalid_categories)} | "
                        f"Valid values: {', '.join(valid_poi_category_osm)} | all"
                    )
                )

    else:
        # nessun OSM passato
        if not has_custom:
            # niente custom → default = ALL OSM
            poi_category_osm_list = valid_poi_category_osm.copy()
        else:
            # solo custom → niente OSM
            poi_category_osm_list = []

    poi_osm_path = poi.get("poi_osm_path")
    if poi_osm_path:

        if is_minio_path(poi_osm_path):
            check_folder_exists(
                poi_osm_path,
                "ERR_014",
                endpoint_url,
                access_key,
                secret_key
            )

        else:
            # path locale
            if not os.path.exists(poi_osm_path):
                raise_error("ERR_014", extra=poi_osm_path)

    # Validate custom POI
    custom_names = ["".join(x.lower().split()) for x in poi_category_custom_name.split(",")] if poi_category_custom_name else []
    custom_csvs = [x.strip() for x in poi_category_custom_csv.split(",")] if poi_category_custom_csv else []
    custom_styles = [x.strip() for x in poi_category_custom_style.split(",")] if poi_category_custom_style else []

    osm_names = ["".join(x.lower().split()) for x in poi_category_osm.split(",")] if poi_category_osm else []
    conflicting_custom = [name for name in custom_names if name in osm_names]
    if conflicting_custom:
        raise_error("ERR_015", extra=f"{', '.join(conflicting_custom)}")

    if custom_names or custom_csvs:
        if len(custom_names) != len(custom_csvs):
            raise_error("ERR_016")

    # CSV existence check
    if custom_names or custom_csvs:
        for f in custom_csvs:
            if is_minio_path(f):
                check_path_exists(f, "ERR_017", endpoint_url, access_key, secret_key)
            else:
                if not os.path.exists(f):
                    raise_error("ERR_017", extra=f)

    # STYLE CONTROLS (custom)
    if custom_styles:
        if not custom_csvs:
            raise_error("ERR_018")

        if len(custom_styles) > len(custom_csvs):
            raise_error("ERR_019")

        for s in custom_styles:
            if is_minio_path(s):
                check_path_exists(s, "ERR_020", endpoint_url, access_key, secret_key)
            else:
                if not os.path.isfile(s):
                    raise_error("ERR_020", extra=s)

    # Validate extended POI
    extended_names = ["".join(x.lower().split()) for x in poi_category_extended_name.split(",")] if poi_category_extended_name else []
    extended_csvs = [x.strip() for x in poi_category_extended_csv.split(",")] if poi_category_extended_csv else []
    extended_styles = [x.strip() for x in poi_category_extended_style.split(",")] if poi_category_extended_style else []

    if extended_names or extended_csvs:
        if len(extended_names) != len(extended_csvs):
            raise_error("ERR_021")

    # CSV existence check
    if extended_names or extended_csvs:
        for f in extended_csvs:
            if is_minio_path(f):
                check_path_exists(f, "ERR_022", endpoint_url, access_key, secret_key)
            else:
                if not os.path.exists(f):
                    raise_error("ERR_022", extra=f)

    # STYLE CONTROLS (extended)
    if extended_styles:
        if not extended_csvs:
            raise_error("ERR_023")

        if len(extended_styles) > len(extended_csvs):
            raise_error("ERR_024")

        for s in extended_styles:
            if is_minio_path(s):
                check_path_exists(s, "ERR_025", endpoint_url, access_key, secret_key)
            else:
                if not os.path.isfile(s):
                    raise_error("ERR_025", extra=s)

    # -------------------
    # PARK
    # -------------------
    park_source = park.get("park_gates_source")
    valid_park_source = ["osm", "csv", "road_intersect", "virtual"]
    if park_source:
        if park_source not in valid_park_source:
            raise_error("ERR_026", extra=f"{'| '.join(valid_park_source)}")

    park_csv = (park.get("park_gates_csv") or "").strip()

    if park_source == "csv":
        if not park_csv:
            raise_error("ERR_027", extra=park_csv)

        if is_minio_path(park_csv):
            check_path_exists(park_csv, "ERR_027", endpoint_url, access_key, secret_key)
        else:
            if not os.path.isfile(park_csv):
                raise_error("ERR_027", extra=park_csv)

    # -------------------
    # GRID
    # -------------------
    clip_layer = grid.get("clip_layer")

    if clip_layer:
        if is_minio_path(clip_layer):
            check_path_exists(clip_layer, "ERR_028", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(clip_layer):
                raise_error("ERR_028", extra=clip_layer)

    grid_gpkg = grid.get("grid_gpkg")

    if grid_gpkg:
        if is_minio_path(grid_gpkg):
            check_path_exists(grid_gpkg, "ERR_029", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(grid_gpkg):
                raise_error("ERR_029", extra=grid_gpkg)

    # -------------------
    # OUTPUT FORMAT / EPSG
    # -------------------
    output_format = execution.get('output_format')
    output_epsg = execution.get('output_epsg')

    if output_format:
        if output_format not in ["csv", "gpkg", "geojson"]:
            raise_error("ERR_007", extra="csv | gpkg | geojson")

    if output_epsg:
        try:
            CRS.from_epsg(output_epsg)
        except (CRSError, ValueError, TypeError):
            raise_error(
                "ERR_008",
                extra="must be a valid EPSG code (e.g., 3857, 4326, 32632)"
            )

    # GeoJSON must be EPSG:4326
    if output_format == "geojson" and output_epsg and int(output_epsg) != 4326:
        raise_error("ERR_009")

    return params
    
# ------------------------------------------------
# PARAMETERS VALIDATION
# ------------------------------------------------
def validate_parameters(parameters_file):

    aoi_parameters = read_param(parameters_file, 'aoi')
    execution_parameters = read_param(parameters_file, 'execution')

    try:
        network_parameters = read_param(parameters_file, 'network')
    except:
        network_parameters = {}

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

    # MinIO keys check
    if execution_parameters.get('output_minio_path'):
        access_key = os.getenv("MINIO_ACCESS_KEY")
        secret_key = os.getenv("MINIO_SECRET_KEY")
        endpoint_url = os.getenv("MINIO_ENDPOINT_URL")

        if not access_key or not secret_key or not endpoint_url:
            raise_error("ERR_004")
    else:
        access_key = None
        secret_key = None
        endpoint_url = None

    # ENUM validation
    weight = execution_parameters.get('weight')
    if weight:
        if weight not in ["time", "distance"]:
            raise_error("ERR_005", extra="time | distance")

    mode = execution_parameters.get('mode')
    if mode:
        if mode not in ["walk", "bike"]:
            raise_error("ERR_006", extra="walk | bike")

    # -------------------
    # NETWORK
    # -------------------
    network_nodes = network_parameters.get("network_nodes")

    if network_nodes:
        if is_minio_path(network_nodes):
            check_path_exists(
                network_nodes,
                "ERR_010",
                endpoint_url,
                access_key,
                secret_key
            )
        else:
            if not os.path.isfile(network_nodes):
                raise_error("ERR_010", extra=network_nodes)

    network_edges = network_parameters.get("network_edges")

    if network_edges:
        if is_minio_path(network_edges):
            check_path_exists(
                network_edges,
                "ERR_011",
                endpoint_url,
                access_key,
                secret_key
            )
        else:
            if not os.path.isfile(network_edges):
                raise_error("ERR_011", extra=network_edges)

    if (network_nodes and not network_edges) or (network_edges and not network_nodes):
        raise_error("ERR_012")

    # -------------------
    # POI
    # -------------------
    try:
        poi_parameters = read_param(parameters_file, 'poi')
    except:
        poi_parameters = {}

    poi_category_osm = poi_parameters.get('poi_category_osm')
    poi_category_custom_name = poi_parameters.get('poi_category_custom_name')
    poi_category_custom_csv = poi_parameters.get('poi_category_custom_csv')
    poi_category_custom_style = poi_parameters.get('poi_category_custom_style')

    poi_category_extended_name = poi_parameters.get('poi_category_extended_name')
    poi_category_extended_csv = poi_parameters.get('poi_category_extended_csv')
    poi_category_extended_style = poi_parameters.get('poi_category_extended_style')

    with open("./config/poi_category_osm_tag.json", "r", encoding="utf-8") as f:
        osm_tags = json.load(f)

    # Valid OSM categories
    valid_poi_category_osm = set(osm_tags.keys()) | {"all"}

    # --- OSM CATEGORY HANDLING ---
    has_osm = bool(poi_category_osm and poi_category_osm.strip())
    has_custom = bool(poi_category_custom_name and poi_category_custom_name.strip())

    if has_osm:

        if poi_category_osm.lower().strip() == "all":
            poi_category_osm_list = valid_poi_category_osm.copy()

        else:
            poi_category_osm_list = [
                c.strip().lower()
                for c in poi_category_osm.split(",")
                if c.strip()
            ]

            invalid_categories = [
                c for c in poi_category_osm_list
                if c not in valid_poi_category_osm
            ]

            if invalid_categories:
                raise_error(
                    "ERR_013",
                    extra=(
                        f"Invalid POI category(ies): {', '.join(invalid_categories)} | "
                        f"Valid values: {', '.join(valid_poi_category_osm)} | all"
                    )
                )

    else:
        # nessun OSM passato
        if not has_custom:
            # niente custom → default = ALL OSM
            poi_category_osm_list = valid_poi_category_osm.copy()
        else:
            # solo custom → niente OSM
            poi_category_osm_list = []

    poi_osm_path = poi_parameters.get("poi_osm_path")
    if poi_osm_path:

        if is_minio_path(poi_osm_path):
            check_folder_exists(
                poi_osm_path,
                "ERR_014",
                endpoint_url,
                access_key,
                secret_key
            )
        else:
            # path locale
            if not os.path.exists(poi_osm_path):
                raise_error("ERR_014", extra=poi_osm_path)

    # Validate custom POI
    custom_names = ["".join(x.lower().split()) for x in poi_category_custom_name.split(",")] if poi_category_custom_name else []
    custom_csvs = [x.strip() for x in poi_category_custom_csv.split(",")] if poi_category_custom_csv else []
    custom_styles = [x.strip() for x in poi_category_custom_style.split(",")] if poi_category_custom_style else []

    osm_names = ["".join(x.lower().split()) for x in poi_category_osm.split(",")] if poi_category_osm else []
    conflicting_custom = [name for name in custom_names if name in osm_names]
    if conflicting_custom:
        raise_error("ERR_015", extra=f"{', '.join(conflicting_custom)}")

    if custom_names or custom_csvs:
        if len(custom_names) != len(custom_csvs):
            raise_error("ERR_016")

    # CSV existence check (custom)
    if custom_names or custom_csvs:
        for f in custom_csvs:
            if is_minio_path(f):
                check_path_exists(f, "ERR_017", endpoint_url, access_key, secret_key)
            else:
                if not os.path.exists(f):
                    raise_error("ERR_017", extra=f)

    # STYLE CONTROLS (custom)
    if custom_styles:
        if not custom_csvs:
            raise_error("ERR_018")

        if len(custom_styles) > len(custom_csvs):
            raise_error("ERR_019")

        for s in custom_styles:
            if is_minio_path(s):
                check_path_exists(s, "ERR_020", endpoint_url, access_key, secret_key)
            else:
                if not os.path.isfile(s):
                    raise_error("ERR_020", extra=s)

    # Validate extended POI
    extended_names = ["".join(x.lower().split()) for x in poi_category_extended_name.split(",")] if poi_category_extended_name else []
    extended_csvs = [x.strip() for x in poi_category_extended_csv.split(",")] if poi_category_extended_csv else []
    extended_styles = [x.strip() for x in poi_category_extended_style.split(",")] if poi_category_extended_style else []

    if extended_names or extended_csvs:
        if len(extended_names) != len(extended_csvs):
            raise_error("ERR_021")

    # CSV existence check (extended)
    if extended_names or extended_csvs:
        for f in extended_csvs:
            if is_minio_path(f):
                check_path_exists(f, "ERR_022", endpoint_url, access_key, secret_key)
            else:
                if not os.path.exists(f):
                    raise_error("ERR_022", extra=f)

    # STYLE CONTROLS (extended)
    if extended_styles:
        if not extended_csvs:
            raise_error("ERR_023")

        if len(extended_styles) > len(extended_csvs):
            raise_error("ERR_024")

        for s in extended_styles:
            if is_minio_path(s):
                check_path_exists(s, "ERR_025", endpoint_url, access_key, secret_key)
            else:
                if not os.path.isfile(s):
                    raise_error("ERR_025", extra=s)

    # -------------------
    # PARK
    # -------------------
    try:
        park_parameters = read_param(parameters_file, 'park')
    except:
        park_parameters = {}

    park_source = park_parameters.get('park_gates_source')
    valid_park_source = ["osm", "csv", "road_intersect", "virtual"]
    if park_source:
        if park_source not in valid_park_source:
            raise_error("ERR_026", extra=f"{'| '.join(valid_park_source)}")

    park_csv = park_parameters.get('park_gates_csv', '').strip()

    if park_source == "csv":
        if not park_csv:
            raise_error("ERR_027", extra=park_csv)

        if is_minio_path(park_csv):
            check_path_exists(park_csv, "ERR_027", endpoint_url, access_key, secret_key)
        else:
            if not os.path.isfile(park_csv):
                raise_error("ERR_027", extra=park_csv)

    # -------------------
    # GRID
    # -------------------
    try:
        grid_parameters = read_param(parameters_file, 'grid')
    except:
        grid_parameters = {}

    clip_layer = grid_parameters.get('clip_layer')

    if clip_layer:
        if is_minio_path(clip_layer):
            check_path_exists(clip_layer, "ERR_028", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(clip_layer):
                raise_error("ERR_028", extra=clip_layer)

    grid_gpkg = grid_parameters.get('grid_gpkg')
    if grid_gpkg:
        if is_minio_path(grid_gpkg):
            check_path_exists(grid_gpkg, "ERR_029", endpoint_url, access_key, secret_key)
        else:
            if not os.path.exists(grid_gpkg):
                raise_error("ERR_029", extra=grid_gpkg)

    # -------------------
    # OUTPUT FORMAT / EPSG
    # -------------------
    output_format = execution_parameters.get('output_format')
    output_epsg = execution_parameters.get('output_epsg')

    if output_format:
        if output_format not in ["csv", "gpkg", "geojson"]:
            raise_error("ERR_007", extra="csv | gpkg | geojson")

    if output_epsg:
        try:
            CRS.from_epsg(output_epsg)
        except (CRSError, ValueError, TypeError):
            raise_error(
                "ERR_008",
                extra="must be a valid EPSG code (e.g., 3857, 4326, 32632)"
            )

    # GeoJSON must be EPSG:4326
    if output_format == "geojson" and output_epsg and int(output_epsg) != 4326:
        raise_error("ERR_009")

    return {
        "aoi": aoi_parameters,
        "poi": poi_parameters,
        "network": network_parameters,
        "park": park_parameters,
        "grid": grid_parameters,
        "execution": execution_parameters
    }
