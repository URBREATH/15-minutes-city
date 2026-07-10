#IMPORT
#---------------
import geopandas
from scipy.spatial import cKDTree
import numpy as np
import pandas as pd
import pandana
import osmnet
from pandana.loaders import osm
import rtree
import warnings
import csv
import time
from pyproj import Transformer
import pyproj
import os
import json
import requests
import shapely
from shapely.ops import split
from shapely.geometry import Point,LineString,box
#from osgeo import gdal
import zipfile
from geovoronoi import voronoi_regions_from_coords, points_to_coords
from shapely import wkt
from urllib.error import HTTPError
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
import subprocess
import math
import urllib3
import warnings
from shapely.ops import transform
from shapely import wkt
from pyproj import Proj, transform
import ast
from shapely.geometry import Polygon, box
from .park_gates import gates_a, gates_b, gates_c
from requests.exceptions import HTTPError
from OSMPythonTools.overpass import Overpass, overpassQueryBuilder
import shutil
import warnings
import tempfile
import glob
from io import BytesIO
import random
from scripts.logger import logger


import osmnx as ox

from scripts.storage_minio import is_minio_path, split_path
#rom scripts.storage_minio import list_minio_categories_wrapper,read_csv_any,upload_if_needed,copy_from_minio,minio_copy_file,upload_on_minio,get_folder,split_path,get_s3_client,minio_file_exists,minio_copy_prefix,minio_list_poi_categories,is_minio_path,split_bucket_and_prefix,load_pois_from_minio
warnings.filterwarnings("ignore")


# GLOBAL
#---------------------

TEMPOMAX = 60 #min
CRS_3857 = 3857
EPSG_4326 = 'EPSG:4326'
CRS_4326 = 4326
EPSG_GATE = 'EPSG:4326'
EPSG_METRIC = 'EPSG:3857'
COEFFICIENT_WALK = 6 #km/h
COEFFICIENT_BIKE = 18 #km/h


# Vedi: https://osmnx.readthedocs.io/en/stable/user-reference.html
osmnet.config.settings.log_console = True
osmnet.config.settings.log_file = False

# -----------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------
# UTILITY FUNCTIONS

# area = [aoi_bbox, aoi_bbox, aoi_bbox, aoi_bbox] in EPSG:4326
# lat_meters = length in meters of a vertical linear element located near the bbox (radii, buffers, etc.)
# lat1 = latitude of the bbox (area) center
# lon  = longitude of the bbox (area) center
# (x, y1) = coordinates of the bbox center in EPSG:3003, also representing the first endpoint of the vertical linear working element
# (x, y2) = coordinates of the second endpoint of the vertical linear working element
# lat2 - lat1 = latitude extent (in degrees, EPSG:4326) of the vertical linear working element


def latitudine_gradi(area, lat_metri):
    lat1 = (area[2]+area[0])/2
    lon = (area[3]+area[1])/2
    transformer = Transformer.from_crs(EPSG_4326,EPSG_METRIC)
    x,y1 = transformer.transform(lat1, lon) #meters
    y2 = y1 + lat_metri #meters
    transformer = Transformer.from_crs(EPSG_METRIC,EPSG_4326)
    lat2, lon = transformer.transform(x, y2) #gradi
    return((lat2-lat1))
    
def longitudine_gradi(area, lon_metri):
    lon1 = (area[3]+area[1])/2
    lat = (area[2]+area[0])/2
    transformer = Transformer.from_crs(EPSG_4326,EPSG_METRIC)
    x1,y = transformer.transform(lat, lon1) #meters
    x2 = x1 + lon_metri #meters
    transformer = Transformer.from_crs(EPSG_METRIC,EPSG_4326)
    lat, lon2 = transformer.transform(x2, y) #gradi
    return((lon2-lon1))


# vale f(0 <= x <= 15) = 1, f(15 < x <= 30) = decade da 1 a 0, f(x > 30) = 0
def decay(time):
    if(time==None): return 0
    elif (time >15 and time <=30): return (-1 * time / 15 + 2)
    elif(time >= 0 and time <=15): return 1
    else: return 0

# User Agent per il blocco delle chiamate overpass
def overpass_query(bbox,query):

    
    overpass = Overpass()
    response = overpass.query(query, timeout=200)

    return response

def overpass_node_query(south, west, north, east, tag_query):

    
    query = f"""
    [out:json][timeout:180];
    (
      node({south},{west},{north},{east})[{tag_query}];
    );
    out geom;
    """
    
    
    headers = {
        "User-Agent": os.environ.get(
            "OSM_USER_AGENT",
            "15min-tool (contact: chiara savoldi)"
        ),
        "Accept": "application/json",
        "Referer": "https://www.dedanext.it/topic-citta-15-minuti/"
    }


    r = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers=headers
    )
    data = r.json()
  
    nodes = []
    for el in data.get("elements", []):
        if el["type"] == "node":
            nodes.append({
                "id": el["id"],
                "lat": el["lat"],
                "lon": el["lon"],
                **el.get("tags", {})
            })

    return pd.DataFrame(nodes)




# -----------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------
# BBOX

def create_bbox(bbox, output_path, hex_diameter_m):
    grid_folder = os.path.join(output_path, "grid")
    csv_path = os.path.join(grid_folder, "grid_parameter.csv")

    if os.path.exists(grid_folder):
        logger.info(f"The folder {grid_folder} already exists.\n")
        return grid_folder   
    latoXCella = 3 / 2 * hex_diameter_m
    latoYCella = np.sqrt(3) / 2 * hex_diameter_m
    latitude = latitudine_gradi(bbox, latoYCella)
    longitude = longitudine_gradi(bbox, latoXCella)

    riga_bbox = [
        "[" + ",".join(str(el) for el in bbox) + "]",
        "[" + ",".join(str(el) for el in bbox) + "]",
        latitude, longitude, hex_diameter_m / 2,
    ]

    os.makedirs(grid_folder)
    np.savetxt(
        csv_path, [riga_bbox], delimiter=';', fmt='%s',
        header='inputBBox;downloadBBox;latitude;longitude;hex_radius_m',
        comments='',
    )
    return grid_folder



# -----------------------------------------------------------------------------------------------------------------------------------

# DOWNLOAD

def download(
    aoi_bbox,
    output_path_bbox,
    poi_category_custom_name,
    poi_category_custom_csv,    
    poi_category_osm,
    poi_category_extended_name,
    poi_category_extended_csv,    
    network_edges,              # path locale o None
    network_nodes,              # path locale o None
    poi_osm_path,               # path locale o None
    mode='walk',
    weight='time',
    park_gates_source='osm',
    park_gates_osm_buffer_m=10,
    park_gates_csv=None,        # path locale o None
    park_gates_virtual_distance_m=100,
):
    aoi_bbox = json.loads(aoi_bbox)

    download_network_osm(
        aoi_bbox, output_path_bbox,
        network_edges, network_nodes, mode, weight,
    )
    download_poi_osm(
        aoi_bbox, output_path_bbox,
        poi_category_osm, poi_osm_path,
        poi_category_custom_name, poi_category_custom_csv,poi_category_extended_name,
        poi_category_extended_csv, 
        park_gates_source, park_gates_osm_buffer_m,
        park_gates_csv, park_gates_virtual_distance_m,
    )
    return 0


    
def download_poi_osm(
    aoi_bbox,
    output_path_bbox,
    poi_category_osm,
    poi_osm_path,           
    custom_names,
    custom_csvs,         
    extended_names,
    extended_csvs,
    park_gates_source='osm',
    park_gates_osm_buffer_m=10,
    park_gates_csv=None,    # path locale o None
    park_gates_virtual_distance_m=100,
):
    logger.info("DOWNLOAD POIs start.")
    logger.info("-" * 120)

    def parse_categories(poi_category_osm, valid_categories):
        if poi_category_osm is None:
            return set()
        if (not poi_category_osm) or (poi_category_osm.lower().strip() == "all"):
            return set(valid_categories)
        return {x.strip().lower() for x in poi_category_osm.split(";") if x.strip()}

    def list_local_categories(folder):
        if not folder or not os.path.exists(folder):
            return set()
        return {os.path.splitext(f)[0] for f in os.listdir(folder) if f.endswith(".csv")}

    poi_folder = os.path.join(output_path_bbox, "osm_poi")
    custom_poi_folder = os.path.join(output_path_bbox, "custom_poi")
    extended_poi_folder = os.path.join(output_path_bbox, "extended_poi")  
    os.makedirs(poi_folder, exist_ok=True)
    os.makedirs(custom_poi_folder, exist_ok=True)
    os.makedirs(extended_poi_folder, exist_ok=True)  

    with open("./config/poi_category_osm_tag.json", "r", encoding="utf-8") as f:
        osm_tags = json.load(f)
    valid_categories = set(osm_tags.keys())

    requested_categories = parse_categories(poi_category_osm, valid_categories)
    logger.info(f"Requested categories: {requested_categories}")

    available_categories = set()
    if poi_osm_path:
        logger.info(f"poi_osm_path: {poi_osm_path}")
        available_categories = list_local_categories(poi_osm_path)

    available_categories = {
        c.lower().strip() for c in available_categories
        if c.lower().strip() in valid_categories
    }
    logger.info(f"Available categories: {available_categories}")

    already_available  = requested_categories & available_categories
    missing_categories = requested_categories - available_categories
    logger.info(f"Already available: {already_available}")
    logger.info(f"Missing categories: {missing_categories}")

    # ---------- COPY EXISTING POIs ----------
    for cat in already_available:
        local_destination = os.path.join(poi_folder, f"{cat}.csv")
        source_path = os.path.join(poi_osm_path, f"{cat}.csv")
        shutil.copy2(source_path, local_destination)
        logger.info(f"Using existing POI: {cat}")

    # ---------- DOWNLOAD MISSING ----------
    for osm_cat in missing_categories:
        logger.info(f"Downloading missing category: {osm_cat}")
        local_csv_path = os.path.join(poi_folder, f"{osm_cat}.csv")
        dfs = []
        for key, values in osm_tags[osm_cat].items():
            tag_query = f'"{key}"~"{"|".join(values)}"'
            logger.info(f"Query: {tag_query}")
            for attempt in range(2):
                try:
                    df = overpass_node_query(
                        aoi_bbox[0], aoi_bbox[1], aoi_bbox[2], aoi_bbox[3], tag_query,
                    )
                    if df is None or df.empty:
                        df = pd.DataFrame(columns=["id", "lat", "lon"])
                    dfs.append(df)
                    break
                except Exception as e:
                    logger.warning(f"Retry {attempt+1} failed for {osm_cat}: {e}")
                    time.sleep(5)

        result = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(
            columns=["id", "lat", "lon"]
        )
        result.to_csv(local_csv_path, index=False)
        logger.info(f"Saved {local_csv_path}")

    # ---------- PARK ----------
    if "park" in missing_categories:
        handle_park_category(
            poi_folder,
            aoi_bbox,
            output_path_bbox,
            park_gates_source,
            park_gates_csv,
            park_gates_osm_buffer_m,
            park_gates_virtual_distance_m,
        )

    # ---------- CUSTOM POIs ----------
    if custom_names and custom_csvs:
        for name, csv_file in zip(custom_names, custom_csvs):
            logger.info(f"Processing custom POI: {name}")
            local_csv_path = os.path.join(custom_poi_folder, f"{name}.csv")
            df = pd.read_csv(csv_file)
            logger.info(f"Rows: {len(df)}")
            df.to_csv(local_csv_path, index=False)
            logger.info(f"Saved custom POI: {local_csv_path}")

    # ---------- extended POIs ----------
    if extended_names and extended_csvs:
        for name, csv_file in zip(extended_names, extended_csvs):
            logger.info(f"Processing extended POI: {name}")
            local_csv_path = os.path.join(extended_poi_folder, f"{name}.csv")
            df = pd.read_csv(csv_file)
            logger.info(f"Rows: {len(df)}")
            df.to_csv(local_csv_path, index=False)
            logger.info(f"Saved extended POI: {local_csv_path}")

    logger.info("-" * 120)
    logger.info("DOWNLOAD POIs end.")
    return 0

def handle_park_category(
    poi_folder,
    bbox_tassello,
    output_path_bbox,
    park_gates_source,
    park_gates_csv,         
    park_gates_osm_buffer_m,
    park_gates_virtual_distance_m,
):
    park_path = os.path.join(poi_folder, "park.csv")
    logger.info("Downloading park from OSM and handling park gates...")

    try:
        if park_gates_source == 'osm':
            with open("./config/park_gate_osm_tag.json", "r", encoding="utf-8") as f:
                gate_tags = json.load(f)
            all_gates = []
            for key, values in gate_tags["gate"].items():
                for value in values:
                    tag_query = f'"{key}"="{value}"'
                    df = safe_osm_query(bbox_tassello, tags=tag_query)
                    all_gates.append(df)
            gates = pd.concat(all_gates, ignore_index=True)

            logger.info("-" * 120)
            logger.info(f"Found {len(gates)} park gates from OSM")

            park = handle_gates(
                "A", bbox_tassello, output_path_bbox, gates,
                None, None, park_path, park_gates_osm_buffer_m, None,
            )
            logger.info("-" * 120)

        elif park_gates_source == 'csv' and park_gates_csv:
            park = pd.read_csv(park_gates_csv)
            logger.info("-" * 120)
            logger.info(f"Loaded {len(park)} park gates from CSV")
            park.to_csv(park_path, index=False)
            logger.info("-" * 120)

        elif park_gates_source == 'road_intersect':
            park = handle_gates(
                "road_intersect", bbox_tassello, output_path_bbox,
                None, None, None, park_path, None, None,
            )

        elif park_gates_source == 'virtual':
            park = handle_gates(
                "virtual", bbox_tassello, output_path_bbox,
                None, None, None, park_path, None, park_gates_virtual_distance_m,
            )

        park.to_csv(park_path, index=False)

    except RuntimeError as e:
        logger.info(e)
        np.savetxt(park_path, ['id,lat,lon,amenity'], delimiter=';', fmt='%s')

    except (HTTPError, requests.exceptions.RequestException) as e:
        logger.info(e)
        
def gates_calculation(park_gdf, gates_df, output_path_bbox, park_gates_osm_buffer_m, park_gates_virtual_distance_m, streets=None, gate_source='A'):
    

    if gates_df is not None:
    
        gates_df = gates_df.copy()
    
        # Rimuove lat/lon mancanti
        gates_df = gates_df.dropna(subset=['lat', 'lon'])
    
        # crea geometria
        gates_df['geometry'] = geopandas.points_from_xy(
            gates_df['lon'], gates_df['lat']
        )
    
        # GeoDataFrame
        gates_gdf = geopandas.GeoDataFrame(
            gates_df,
            geometry='geometry',
            crs=EPSG_4326
        )
    
        gates_gdf = gates_gdf.to_crs(EPSG_METRIC)
        gates_gdf = gates_gdf.reset_index(drop=True)
    
        # filtra geometrie valide
        gates_gdf = gates_gdf[gates_gdf.geometry.notna()]
    
    else:
        gates_gdf = geopandas.GeoDataFrame(
            columns=["lat", "lon", "geometry", "unique_id"],
            geometry="geometry",
            crs=EPSG_METRIC
        )
    
    if 'unique_id' not in gates_gdf.columns:
        gates_gdf['unique_id'] = range(1, len(gates_gdf) + 1)
                   
    # Per le aree verdi
    if 'unique_id' not in park_gdf.columns:
        park_gdf = park_gdf.copy()
        park_gdf['unique_id'] = range(1, len(park_gdf)+1)



    # Per le streets (se servono)
    if streets is not None and 'unique_id' not in streets.columns:
        streets = streets.copy()
        streets['unique_id'] = range(1, len(streets)+1)
    else:
        streets = geopandas.GeoDataFrame(
        columns=["id", "highway", "cycleway", "footway", "oneway", "bicycle", "geometry", "unique_id"],
        geometry="geometry"
        )
     
    # Algoritmo di calcolo gate

    if gate_source == 'A':        
        # Creazione layer QGIS

        result_gdf = gates_a(
            green=park_gdf,
            gates=gates_gdf,
            id_green_area="unique_id",
            buffer_m=park_gates_osm_buffer_m
        )

    elif gate_source == 'road_intersect':  # tipo B/C o ABC
        

        result_gdf = gates_b(
            green=park_gdf,
            streets=streets,
            id_green_area="unique_id"
        )
    else:
        result_gdf = gates_c(
            green=park_gdf,
            id_green_area="unique_id",
            distance_m=park_gates_virtual_distance_m
        )
 
 
    if result_gdf is not None and not result_gdf.empty:
    
        result_gdf = result_gdf.to_crs(EPSG_4326)   
        result_gdf["lon"] = result_gdf.geometry.x
        result_gdf["lat"] = result_gdf.geometry.y
             
    else:
        logger.info("[ERROR] generating gates, empty CSV saved")
        result_gdf = pd.DataFrame(columns=["lat","lon","amenity"])
              
    return result_gdf



# ------------------------------------------------------------
# Funzione per evitare troppe richieste OSM
# ------------------------------------------------------------
    
def safe_osm_query(aoi_bbox_4326, tags, pause=15, max_retries=8):

    # costruisci query
    south, west, north, east = aoi_bbox_4326
    query = f"""
    (
      node({south},{west},{north},{east})[{tags}];
    );
    out geom;
    """

    for attempt in range(max_retries):
        try:
            response = overpass_query(aoi_bbox_4326,query)
            
            # Se Overpass restituisce oggetti, anche vuoti → stop retry
            data = []
            for el in response.elements():
                geom = el.geometry()
                
                if geom:
                    shp = shapely.geometry.shape(geom)
                    data.append({
						"id": el.id(),
						"lat": el.lat(),
						"lon": el.lon(),
						"barrier": el.tag('barrier'),
						"entrance": el.tag('entrance'),
                        "geometry": shp
                    })

            if not data:
                logger.info(f"WARNING: no OSM data for tag {tags}, empty dataframe")
                return geopandas.GeoDataFrame(columns=['id','lat','lon','amenity'], geometry="geometry", crs=EPSG_4326)
            else: 
                return geopandas.GeoDataFrame(data, geometry="geometry", crs=EPSG_4326)

        except Exception as e:
            # retry solo su errori reali
            logger.info(f"[ERROR] querying {tags}: {e} ({attempt+1}/{max_retries})")
            time.sleep(pause)
    else:
        # superato max_retries
        raise RuntimeError(f"Overpass query failed for tag {tags} after {max_retries} attempts")
# ------------------------------------------------------------
# Gestione completa dei gates
# ------------------------------------------------------------
def handle_gates(gate_source, aoi_bbox, output_path_bbox,  gates, park=None, streets=None, park_csv_path_local=None,park_gates_osm_buffer_m = 10, park_gates_virtual_distance_m = 100):
    
    os.makedirs(os.path.dirname(park_csv_path_local), exist_ok=True)

    south, west, north, east = aoi_bbox
    with open("./config/poi_category_osm_tag.json", "r", encoding="utf-8") as f:
        osm_tags = json.load(f)
    park_tags = osm_tags["park"]
    leisure_values = park_tags["leisure"]    
    # Query Overpass: tutti i leisure di interesse
    query_parts = []
    for lv in leisure_values:
        query_parts.append(f'way({south},{west},{north},{east})[leisure={lv}];')

    query = f"""
    (
      {'  '.join(query_parts)}
    );
    out geom;
    """      
    

    for attempt in range(8):
        try:
            result = overpass_query(aoi_bbox,query)
            # Risposta ricevuta → stop retry
            break
        except Exception as e:
            logger.info(f"Park query attempt {attempt+1} failed: {e}")
            time.sleep(15)
    else:
        # Fallito dopo 8 tentativi
        logger.info("download_parks failed after 8 attempts")
        return geopandas.GeoDataFrame(columns=["id", "amenity", "geometry"], geometry="geometry", crs=EPSG_METRIC)

    # Costruisci GeoDataFrame
    data = []
    for el in result.elements():
        geom = el.geometry()
        if geom:
            shape = shapely.geometry.shape(geom)
            if shape.geom_type in ["Polygon", "MultiPolygon"]:
                data.append({
                    "id": el.id(),
                    "amenity": el.tag("leisure"),
                    "geometry": shape
                })

    # Se non ci sono elementi
    if not data:
        return geopandas.GeoDataFrame(columns=["id", "amenity", "geometry"], geometry="geometry", crs=EPSG_METRIC)

    park = geopandas.GeoDataFrame(data, geometry="geometry", crs=EPSG_GATE)
    park = park.to_crs(EPSG_METRIC)

    #logger.info(park)
    if gate_source == "A":    
        result_gdf = gates_calculation(park, gates,output_path_bbox,park_gates_osm_buffer_m, park_gates_virtual_distance_m, None, gate_source)
    elif gate_source == "road_intersect":
        if streets is None:
            streets = download_streets(aoi_bbox)           
            streets = streets.set_crs(EPSG_GATE)
            streets = streets.to_crs(EPSG_METRIC)        
        result_gdf = gates_calculation(park, None, output_path_bbox, park_gates_osm_buffer_m, park_gates_virtual_distance_m, streets, gate_source)
    else:
        result_gdf = gates_calculation(park, None, output_path_bbox,park_gates_osm_buffer_m, park_gates_virtual_distance_m, None, gate_source)
    
    #result_gdf.to_csv(park_csv_path_local, index=False)
    return result_gdf


def download_streets(bbox):

    # Query Overpass: tutte le way con qualunque valore di 'highway'
    south, west, north, east = bbox
    query = f"""
    (
      way({south},{west},{north},{east})[highway];
      way({south},{west},{north},{east})[cycleway];
      way({south},{west},{north},{east})[footway];
      way({south},{west},{north},{east})[bicycle];	  
    );
    out geom;
    """
    

    for attempt in range(8):
        try:
            result =  overpass_query(bbox,query)
            # Risposta ricevuta con codice 200 → interrompo i retry
            break
        except Exception as e:
            logger.info(f"Attempt {attempt+1} failed: {e}")
            time.sleep(15)
    else:
        logger.info("download_streets failed after 8 attempts")
        return geopandas.GeoDataFrame(columns=["id", "highway", "cycleway", "footway", "oneway", "bicycle", "geometry"], geometry="geometry")
        
    data = []

    for el in result.elements():
        geom = el.geometry()
        if geom:
            shape = shapely.geometry.shape(geom)
            if shape.geom_type in ["LineString", "MultiLineString"]:
                data.append({
                    "id": el.id(),
                    "highway": el.tag("highway"),
                    "cycleway": el.tag("cycleway"),
                    "footway": el.tag("footway"),
                    "oneway": el.tag("oneway"), 
                    "bicycle": el.tag("bicycle"),  
                    "geometry": shape
                })


    if data:
        gdf =  geopandas.GeoDataFrame(data, geometry="geometry")
        # Lista dei tipi di strade veicolari/pedonali
        with open("./config/park_road_network_osm_tag.json", "r", encoding="utf-8") as f:
            network_tags = json.load(f)

        # estrai le liste
        highway_types = network_tags["highway_types"]
        footway_types = network_tags["footway_types"]
        cycleway_types = network_tags["cycleway_types"]
        
        
        # Normalizza colonne mancanti:
        for col in ["highway", "cycleway", "footway", "bicycle"]:
            if col not in gdf.columns:
                gdf[col] = None
        
        
        gdf = gdf[
            (gdf["highway"].isin(highway_types)) |
            (gdf["cycleway"].isin(cycleway_types)) |
            (gdf["footway"].isin(footway_types))
        ].copy()

        return gdf
    else:
        return geopandas.GeoDataFrame(columns=["id", "highway", "cycleway", "footway", "oneway", "bicycle", "geometry"], geometry="geometry")



# -----------------------------------------------------------------------------------------------------------------------------------
def download_network_osm(
    aoi_bbox,
    output_path_bbox,
    network_edges,       
    network_nodes,        
    mode='walk',
    weight='time',
):
    logger.info("DOWNLOAD NETWORK start.")
    logger.info("-" * 120)

    local_folder = os.path.join(output_path_bbox, "osm_network")
    os.makedirs(local_folder, exist_ok=True)

    local_nodes = os.path.join(local_folder, "nodes.csv")
    local_edges = os.path.join(local_folder, "edges.csv")

    # -------- REUSE INPUT NETWORK --------
    if network_edges or network_nodes:
        logger.info("Network input specified, skipping OSM generation.")

        if network_edges:
            shutil.copy2(network_edges, local_edges)

        if network_nodes:
            shutil.copy2(network_nodes, local_nodes)

        logger.info("Reused network saved to output.")
        logger.info("DOWNLOAD NETWORK end.")
        return 0

    # -------- GENERATE NETWORK --------
    logger.info("Generating OSM network...")
    _, gdf_nodes, gdf_edges = get_network_osm(aoi_bbox, output_path_bbox)

    if weight == "time":
        _, gdf_edges = calculate_edges_time_from_nodes(gdf_edges, mode=mode)

    gdf_nodes["type"] = "osm"
    gdf_nodes.to_csv(local_nodes, index=False)

    if "time" not in gdf_edges.columns:
        gdf_edges["time"] = np.nan
    gdf_edges[["u", "v", "length", "time"]].to_csv(local_edges, index=False)

    logger.info("Network saved locally.")
    logger.info("DOWNLOAD NETWORK end.")
    return 0

        
# -----------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------


def get_network_osm(aoi_bbox, output_path_bbox, retries=3, sleep_seconds=1):
    last_exc = None

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"OSM network download attempt {attempt}/{retries}")

            south, west, north, east = aoi_bbox

            bbox_osmnx = (west, south, east, north)

            G = ox.graph_from_bbox(
                bbox_osmnx,
                network_type="walk",
                simplify=True
            )
            
            gdf_nodes, gdf_edges = ox.graph_to_gdfs(
                G, nodes=True, edges=True
            )

            # ---------- NODES ----------
            gdf_nodes = (
                gdf_nodes
                .reset_index()
                .rename(columns={"osmid": "id"})
            )

            # ---------- EDGES ----------
            gdf_edges = (
                gdf_edges
                .reset_index()
                .rename(columns={"length": "length"})
            )

            logger.info("OSM network successfully downloaded (osmnx).")
            return 0, gdf_nodes, gdf_edges

        except Exception as e:
            last_exc = e
            logger.warning(f"Attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(sleep_seconds)

    # ------------------------------------------------------------------
    # FALLBACK
    # ------------------------------------------------------------------
    logger.error("All retries failed. Creating empty OSM network.")

    gdf_nodes = geopandas.GeoDataFrame(
        columns=["id", "geometry"],
        geometry="geometry",
        crs=EPSG_4326
    )

    gdf_edges = geopandas.GeoDataFrame(
        columns=["u", "v", "length", "geometry"],
        geometry="geometry",
        crs=EPSG_4326
    )

    return 0, gdf_nodes, gdf_edges



 # -----------------------------------------------------------------------------------------------------------------------------------
 # -----------------------------------------------------------------------------------------------------------------------------------
def crea_linestring(row, nodes):
    u = row['u']
    v = row['v']
    try:
        # Recupera le coordinate dei nodi u e v
        u_x, u_y = nodes.loc[u, 'x'], nodes.loc[u, 'y']
        v_x, v_y = nodes.loc[v, 'x'], nodes.loc[v, 'y']
        return LineString([(u_x, u_y), (v_x, v_y)])
    except Exception as e:
        logger.info(f"[ERROR] during the crea_linestring: {e}.\n")        

# -----------------------------------------------------------------------------------------------------------------------------------


def calculate_edges_time_from_nodes(gdf_edges, mode = 'walk'):  
   
    if mode == 'walk':
        coefficiente = COEFFICIENT_WALK
    else:
        coefficiente = COEFFICIENT_BIKE


    if gdf_edges.empty:
        logger.warning("Edges GeoDataFrame is empty. Skipping time calculation.")

        for col in ['velocita', 'time']:
            if col not in gdf_edges.columns:
                gdf_edges[col] = []

        return 0, gdf_edges
    
           
    gdf_edges['slope'] = 0.0         
    gdf_edges = gdf_edges.dropna(subset=['geometry']) 
                
    slope_abs = gdf_edges['slope'].abs()

    for index, row in gdf_edges.iterrows():
       
        velocita = coefficiente * math.exp(-3.5 * abs(gdf_edges.at[index, 'slope'] + 0.05))
        gdf_edges.at[index, 'velocita'] = velocita * (1000/60)
    
        gdf_edges.at[index, 'time'] = row['length'] / (gdf_edges.at[index, 'velocita'])
                    
    gdf_edges['velocita'] = gdf_edges['velocita'].astype('float32')        
    gdf_edges['time'] = gdf_edges['time'].astype('float32')     
    
    gdf_edges = gdf_edges.sort_values(by=['u', 'v', 'length']) #ordinamento in base alle colonne 'u', 'v' e 'length'.
    
    return 0, gdf_edges


# -----------------------------------------------------------------------------------------------------------------------------------
# WALK SCORE FUNCTION

def walkScore_min(output_path_bbox, poi_category_osm,
                  walk_speed_kmh, bike_speed_kmh,
                  mode='walk', weight='time'):
    walk_speed_kmh = float(walk_speed_kmh)
    bike_speed_kmh = float(bike_speed_kmh)
    if weight == 'time':
        peso = TEMPOMAX
    else:
        if mode == 'walk':
            velocita = walk_speed_kmh / 3.6
            peso = velocita * (TEMPOMAX * 60)
        else:
            velocita = bike_speed_kmh / 3.6
            peso = velocita * (TEMPOMAX * 60)

    nodes = pd.read_csv(f"{output_path_bbox}/osm_network/nodes.csv", index_col=0)
    edges = pd.read_csv(f"{output_path_bbox}/osm_network/edges.csv", index_col=[0, 1])
    edges = edges.reset_index()


    if edges.empty:
        return 0, None

    poi_folder = os.path.join(output_path_bbox, "osm_poi")
    poi_folder_custom = os.path.join(output_path_bbox, "custom_poi")
    extended_poi_folder = os.path.join(output_path_bbox, "extended_poi")
    csv_files = []
    for folder in [poi_folder, poi_folder_custom, extended_poi_folder]:
        if os.path.isdir(folder):
            csv_files.extend(glob.glob(os.path.join(folder, "*.csv")))

#---------------------------
    list_string, pois = [], []
    for f in csv_files:
        list_string.append(os.path.splitext(os.path.basename(f))[0])
        pois.append(pd.read_csv(f))

    logger.info("POIs categories: %s", list_string)
#----------------------------------------------
    if weight == 'time':
        network = pandana.Network(nodes['x'], nodes['y'],
                                  edges['u'], edges['v'],
                                  edges[['time']], twoway=False)
    else:
        network = pandana.Network(nodes['x'], nodes['y'],
                                  edges['u'], edges['v'],
                                  edges[['length']], twoway=False)

    walk_score = nodes
    for i in range(0, len(pois)):
        if not pois[i].empty:
            network.set_pois(category=list_string[i], maxdist=peso, maxitems=1,
                             x_col=pois[i].lon, y_col=pois[i].lat)
            res = network.nearest_pois(distance=peso, category=list_string[i],
                                       num_pois=1, include_poi_ids=False)
            if weight == 'time':
                walk_score[f'minutes_{list_string[i]}'] = res[1]
            else:
                walk_score[f'minutes_{list_string[i]}'] = res[1] / velocita / 60
        else:
            walk_score[f'minutes_{list_string[i]}'] = 60.0

    walk_score = walk_score.replace({60.0: None})

    # -------- SALVATAGGIO MINUTI SUI NODI --------
    try:
        nodes_out_dir = os.path.join(output_path_bbox, "osm_network")

        nodes_csv_path = os.path.join(nodes_out_dir, "nodes_minutes.csv")
        walk_score.to_csv(nodes_csv_path, index=True)

        # GPKG: versione geospaziale (utile per QGIS)
        nodes_gdf = geopandas.GeoDataFrame(
            walk_score.copy(),
            geometry=geopandas.points_from_xy(walk_score['x'], walk_score['y']),
            crs=EPSG_4326,
        )
        nodes_gpkg_path = os.path.join(nodes_out_dir, "nodes_minutes.gpkg")
        nodes_gdf.to_file(nodes_gpkg_path, layer="nodes_minutes", driver="GPKG")

        logger.info("Saved nodes with minutes: %s / %s",
                    nodes_csv_path, nodes_gpkg_path)
    except Exception as e:
        logger.warning("Could not save nodes_minutes: %s", e)
    # ---------------------------------------------

    logger.info('Function walkScore_min completed.\n')
    return 0, walk_score
    

        
#--------------------------------------------------------------------
#-----------------------------------------------------------------       
       
#COMPUTO


def computo(aoi_bbox, latitude, longitude, hex_radius_m, output_path_bbox,
            custom_names, custom_csvs, grid_gpkg, poi_category_osm, clip_layer,
            filename, extended_names, extended_csvs,poi_category_custom_style,poi_category_extended_style,
            output_minio_path,             
            virtual_nodes, output_format, output_EPSG,
            bike_speed_kmh, walk_speed_kmh, mode='walk', weight='time'):

    bbox = json.loads(aoi_bbox)
    grid_folder = os.path.join(output_path_bbox, "grid")
    os.makedirs(grid_folder, exist_ok=True)
    grid = None

    # -------- GRID --------
    if grid_gpkg:
        logger.info(f"Loading existing grid: {grid_gpkg}")
        grid = geopandas.read_file(grid_gpkg).to_crs(EPSG_4326)
        outputPath_grid = os.path.join(grid_folder, "grid.gpkg")
        grid.to_file(outputPath_grid, layer="grid", driver="GPKG")
    else:
        logger.info("Generating grid...")
        lon = []
        lat= []
        rLon = longitudine_gradi(bbox, hex_radius_m )
        rLat =latitudine_gradi(bbox, hex_radius_m )
        nCelleX = round((bbox[3]-bbox[1])/longitude)
        nCelleY = round((bbox[2]-bbox[0])/latitude)
        
        for i in range(int(nCelleY)+1):
            for j in range(int(nCelleX)+1):
                lat.append(bbox[0] + i * latitude)
                lon.append(bbox[1] + j * longitude)
                lat.append(bbox[0] + i * latitude + np.sqrt(3)/2*rLat)
                lon.append(bbox[1] + j * longitude + 3/2*rLon)
        #Creazione dei centri degli esagoni
        centri = pd.DataFrame(columns = ["x","y"])
        
        centri['x'] = lon
        centri['y'] = lat
        for j in centri.index:
            centri.at[j,'geometry'] = "POINT ({} {})".format(centri.at[j,'x'], centri.at[j,'y'])
        gs = geopandas.GeoSeries.from_wkt(centri['geometry'])
        centri = geopandas.GeoDataFrame(centri, geometry=gs, crs=EPSG_4326)
        centri = centri.to_crs(CRS_3857)
        #Voronoi 
        transformer = Transformer.from_crs(EPSG_4326,EPSG_METRIC, always_xy=True)
        xmin,ymin = transformer.transform(bbox[1],bbox[0])
        xmax,ymax = transformer.transform(bbox[3]+1.5*rLon,bbox[2]+np.sqrt(3)/2*rLat)
        boundary_shape = shapely.geometry.box(xmin,ymin,xmax,ymax, ccw=True)
        
        #### ONLY ATHENS
        
        keywords = ["athens", "ath", "athen"]
        ath = False

        for p in [output_path_bbox, output_minio_path]:
            if isinstance(p, str) and any(k in p.lower() for k in keywords):
                ath = True

        if ath:
            boundary_shape = shapely.geometry.box(xmin, ymin, xmax, ymax, ccw=True).buffer(200)
            
            try:
                region_polys, region_pts = voronoi_regions_from_coords(centri.geometry, boundary_shape)
            except Exception as e:
                logger.info("❌ Errore in voronoi_regions_from_coords:", e)
                logger.info("Numero centri:", len(centri))
                logger.info("BBox:", bbox)
                return 1
        #### ONLY ATHENS
        else:
            region_polys, region_pts = voronoi_regions_from_coords(centri.geometry, boundary_shape)  
        geom = list(region_polys.values())
        df = pd.DataFrame(geom, columns=['geometry'])
        grid = geopandas.GeoDataFrame(df, crs=CRS_3857) 
        #eliminazione poligoni al conend
        a = [x for x in range(len(centri)+1-int((nCelleX+1)*2),len(centri),2)]
        b = [x for x in range(0,int(nCelleX+1)*2,2)]
        c = [x for x in range(0,len(centri),int(nCelleX+1)*2)]
        d = [x-1 for x in range(0,len(centri)+1,int(nCelleX+1)*2)]
        IDtoDrop = np.unique(a+b+c+d)
        for i in centri.index:
            if i in IDtoDrop:
            
                centri = (centri.drop(i))
        
        
        #grid = geopandas.sjoin(grid, centri, how='inner', op ='contains')
        grid = geopandas.sjoin(grid, centri, how='inner', predicate='contains')

        bbox = json.loads(aoi_bbox)

        # bbox originale in EPSG:4326 -> la trasformo in EPSG:3857
        xmin0, ymin0 = transformer.transform(bbox[1], bbox[0])  # lon_min, lat_min
        xmax0, ymax0 = transformer.transform(bbox[3], bbox[2])  # lon_max, lat_max
        
        # apotema dell'esagono (hex_radius_m è il raggio): r * sqrt(3)/2
        apotema = float(hex_radius_m) * (np.sqrt(3) / 2.0)
        
        # bbox "interna" (tolgo un apotema su tutti i lati)
        bbox_inner = shapely.geometry.box(
            xmin0 + apotema,
            ymin0 + apotema,
            xmax0 - apotema,
            ymax0 - apotema,
            ccw=True
        )
        
        # tengo solo gli esagoni il cui centroide è dentro la bbox interna
        mask = grid.geometry.centroid.within(bbox_inner)
        grid = grid.loc[mask].copy()
        
        grid = grid.to_crs(CRS_4326)
        
        grid = grid.drop('index_right', axis = 1)
        outputPath_grid = os.path.join(grid_folder, 'grid.gpkg')
        grid.to_file(
        outputPath_grid,
        layer="grid",
        driver="GPKG"
        )

    # -------- WALK SCORE --------
    result, walk_score = walkScore_min(
        output_path_bbox, poi_category_osm,
        walk_speed_kmh, bike_speed_kmh, mode, weight,
    )

    # -------- EMPTY OUTPUT --------
    if walk_score is None or walk_score.empty:
        logger.warning("walkScore_min returned no results. Generating EMPTY output.")
    
        output_dir = os.path.join(output_path_bbox, "output")
        os.makedirs(output_dir, exist_ok=True)
    
        if output_format == "csv":
            result = os.path.join(output_dir, f"{filename}.csv")
            np.savetxt(
                result,
                [],
                delimiter=';',
                fmt='%s',
                header='geometry;overall_average;overall_max',
                comments=''
            )
    
        elif output_format == "geojson":
            empty = geopandas.GeoDataFrame(
                {"overall_average": [], "overall_max": []},
                geometry=[],
                crs=output_EPSG
            )
            result = os.path.join(output_dir, f"{filename}.geojson")
            empty.to_file(result, driver="GeoJSON")
    
        else:  # gpkg (default)
            empty = geopandas.GeoDataFrame(
                {"overall_average": [], "overall_max": []},
                geometry=[],
                crs=output_EPSG
            )
            result = os.path.join(output_dir, f"{filename}.gpkg")
            empty.to_file(result, layer=filename, driver="GPKG")

        if access_key and secret_key and endpoint_url and output_minio_path:
            get_folder(
                output_dir,
                output_minio_path,
                access_key,
                secret_key,
                endpoint_url
            )
    
        return 0
    else:
    # -------- POIs (solo locale ora) --------
        walk_score = geopandas.GeoDataFrame(
            walk_score, geometry=geopandas.points_from_xy(walk_score.x, walk_score.y),
        )
        pois, categories = [], []
        poi_folder = os.path.join(output_path_bbox, "osm_poi")
        custom_poi_folder = os.path.join(output_path_bbox, "custom_poi")
        extended_poi_folder = os.path.join(output_path_bbox, "extended_poi")
        
        extended_categories = set()   # NEW: tiene traccia delle extended
        
        csv_files = []
        for folder in [poi_folder, custom_poi_folder, extended_poi_folder]:
            if os.path.isdir(folder):
                for f in glob.glob(os.path.join(folder, "*.csv")):
                    csv_files.append(f)
                    if folder == extended_poi_folder:           # NEW
                        extended_categories.add(               # NEW
                            os.path.splitext(os.path.basename(f))[0]
                        )
        
        for f in csv_files:
            categories.append(os.path.splitext(os.path.basename(f))[0])
            pois.append(pd.read_csv(f))
        
        # NEW: categorie usate per gli overall (escludono le extended)
        main_categories = [c for c in categories if c not in extended_categories]
        
        logger.info("POIs categories: %s", categories)
        logger.info("Main categories (for overall): %s", main_categories)
        logger.info("extended categories: %s", extended_categories)
    
        # -------- VIRTUAL NODES --------
        if virtual_nodes:
            hexag = geopandas.sjoin(grid, walk_score, how='left', predicate='contains')
            hexag['missing_categories'] = hexag.apply(
                lambda row: [c for c in categories if pd.isna(row.get(f'minutes_{c}'))],
                axis=1,
            )
            empty_hexag = hexag[hexag['missing_categories'].apply(len) > 0].copy()
            centroids_empty_hexag = empty_hexag.copy()
            centroids_empty_hexag['geometry'] = centroids_empty_hexag.geometry.centroid
    
            attach_centroids_to_network(centroids_empty_hexag, output_path_bbox, mode)
    
            result, walk_score = walkScore_min(
                output_path_bbox, poi_category_osm,
                walk_speed_kmh, bike_speed_kmh, mode, weight,
            )
            walk_score = geopandas.GeoDataFrame(
                walk_score,
                geometry=geopandas.points_from_xy(walk_score.x, walk_score.y),
                crs=EPSG_4326,
            )
    
        hexag = geopandas.sjoin(grid, walk_score, how='inner', predicate = 'contains')
     

        hexag = hexag.drop(columns=['highway'], errors='ignore')
        hexag = hexag.drop(columns=['type'], errors='ignore')
        hexag = hexag.drop(columns=['ref'], errors='ignore')
        hexag = hexag.drop(columns=['junction'], errors='ignore')
        hexag = hexag.drop(columns=['railway'], errors='ignore')

        
        hexag = hexag.replace({'NaN' : np.nan})
        hexag = hexag.dissolve(by = hexag.index, aggfunc="mean")
        
        
        for cat in categories:
            if 'minutes_{}'.format(cat) not in hexag.columns:
                hexag['minutes_{}'.format(cat)] = np.nan
        if poi_category_osm != 'all':
            for index, row in hexag.iterrows():
                if pd.notnull(row.get('media', np.nan)):
                    hexag.at[index, f'minutes_{poi_category_osm}'] = row['media']
                    

        # Colonne usate per gli overall: SOLO main_categories
        main_minutes_cols = [f'minutes_{c}' for c in main_categories]
        
        hexag['countNaN'] = hexag[main_minutes_cols].isnull().sum(axis=1)
        
        # Manteniamo TUTTE le colonne minutes_* (anche extended) per visualizzarle
        hexag = hexag[
            ['geometry']
            + [f'minutes_{cat}' for cat in categories]
            + ['countNaN']
        ]
        
        # Calcolo indice continuo (da 0 a 100) — solo se ci sono almeno 2 main categories
        if len(main_categories) > 1:
        
            hexag['overall_average'] = None
        
            for i in hexag.index:
                valori = []
                val100 = []
                num_valori = 0
        
                for cat in main_categories:                          # CHANGED
                    val = hexag.at[i, f'minutes_{cat}']
        
                    if np.isnan(val):
                        valori.append(None)
                    else:
                        valori.append(val)
                        num_valori = len(valori)
        
                    val100.append(decay(val))
        
                if hexag.at[i, 'countNaN'] == len(main_categories):  # CHANGED
                    hexag.at[i, 'overall_average'] = None
                else:
                    if num_valori > 0:
                        hexag.at[i, 'overall_average'] = sum(filter(None, valori)) / num_valori
                    else:
                        hexag.at[i, 'overall_average'] = None
        
            def overall_max(row, cols):
                values = row[cols]
                if values.isnull().any():
                    return '>60'
                max_val = values.max()
                if max_val > 60:
                    return '>60'
                return round(max_val, 2)
        
            hexag['overall_max'] = hexag.apply(
                lambda r: overall_max(r, main_minutes_cols),         
                axis=1,
            )
        
        pd.set_option('display.max_columns', None)
        pd.set_option("display.max_rows", None)        
        minutes_cols = [col for col in hexag.columns if col.startswith('minutes_')]
                                                          
                                                                

        for col in minutes_cols:
            hexag[col] = pd.to_numeric(hexag[col], errors='coerce')
            hexag[col] = hexag[col].round(2)
        
    
                
        hexag = hexag.replace({None : np.nan})
        hexag = hexag.to_crs(CRS_3857) 
        if 'overall_average' in hexag.columns:
            hexag['overall_average'] = hexag['overall_average'].round(2)
            hexag['overall_average'] = hexag['overall_average'].fillna('>60')
        hexag[minutes_cols] = hexag[minutes_cols].fillna('> 60')        

        hexag.rename(
        columns=lambda c: c.replace('minutes_', '') if c.startswith('minutes_') else c,
        inplace=True
        )
        cols_to_keep = ['geometry'] + categories

        # -------- CLIP --------

        main_cols = ['geometry'] + [c for c in main_categories if c in hexag.columns]
        if len(main_categories) > 1:
            for c in ['overall_average', 'overall_max']:
                if c in hexag.columns:
                    main_cols.append(c)
        
        extended_cols = ['geometry'] + [c for c in extended_categories if c in hexag.columns]
        
        # ---------- CLIP (una volta sola, poi si splitta) ----------
        if clip_layer and os.path.isfile(clip_layer):
            cl = geopandas.read_file(clip_layer).to_crs(hexag.crs)
            hexag_clipped = geopandas.clip(hexag, cl)
        else:
            hexag_clipped = hexag.copy()
        
        output_dir = os.path.join(output_path_bbox, "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Subset per i due output
        hexag_main = hexag_clipped[[c for c in main_cols if c in hexag_clipped.columns]].copy()
        hexag_main = hexag_main.to_crs(f"EPSG:{output_EPSG}")
        
        has_extended = bool(extended_categories) and len(extended_cols) > 1
        if has_extended:
            hexag_compl = hexag_clipped[[c for c in extended_cols if c in hexag_clipped.columns]].copy()
            hexag_compl = hexag_compl.to_crs(f"EPSG:{output_EPSG}")
        
        # ---------- SALVATAGGIO ----------
        def _save(gdf, name):
            if output_format == 'gpkg':
                gdf.to_file(f"{output_dir}/{name}.gpkg", layer=f"{name}", driver="GPKG")
            elif output_format == "geojson":
                gdf.to_file(os.path.join(output_dir, f"{name}.geojson"), driver="GeoJSON")
            else:
                gdf.to_csv(f"{output_dir}/{name}.csv", sep=';', index=False)
        
        _save(hexag_main, filename)
        if has_extended:
            _save(hexag_compl, f"{filename}_extended")
        
        # ---------- _publish.json (MAIN: osm + custom + overall) ----------
        if output_minio_path:
            parts = output_minio_path.split("/", 1)[1]
        
            # style_dir esiste già con gli SLD OSM di default
            style_dir = os.path.join(output_path_bbox, "style")
            os.makedirs(style_dir, exist_ok=True)
        
            publish_main  = {"analysis": "15 minutes city index", "data": []}
            publish_compl = {"analysis": "15 minutes city index - extended", "data": []}
        
            # ---- categorie OSM (= main_categories MENO le custom) ----
            osm_categories = [c for c in main_categories if c not in (custom_names or [])]
        
            # ---- voci publish_main per OSM + overall (SLD già in style/) ----
            publish_categories_main = list(osm_categories)
            if len(main_categories) > 1:
                publish_categories_main.extend(["overall_average", "overall_max"])
        
            for cat in publish_categories_main:
                publish_main["data"].append({
                    "workspace": f"{filename}_{cat}",
                    "store_name": f"{filename}_{cat}",
                    "data_path": f"{parts}/output/{filename}.{output_format}",
                    "style_name": cat,
                    "sld_path": f"{parts}/style/{cat}.sld",
                    "write_on_catalogue": True,
                    "description": "15min analysis",
                })
        
            # ---- funzione che copia SLD e aggiunge voce al publish ----
            def _publish_styles(names, styles_str, kind, target_publish, data_filename):
                if not styles_str:
                    return
        
                if isinstance(names, str):
                    names_list = [n.strip() for n in names.split(";") if n.strip()]
                else:
                    names_list = [str(n).strip() for n in (names or []) if str(n).strip()]
        
                styles = [s.strip() for s in styles_str.split(";") if s.strip()]
        
                for i, sld_path in enumerate(styles):
                    if not os.path.isfile(sld_path):
                        logger.warning(f"[{kind}] style not found: {sld_path}")
                        continue
        
                    if i < len(names_list):
                        cat_name = "".join(names_list[i].lower().split())
                    else:
                        cat_name = os.path.splitext(os.path.basename(sld_path))[0]
        
                    dest_sld = os.path.join(style_dir, f"{cat_name}.sld")
                    try:
                        shutil.copy2(sld_path, dest_sld)
                        logger.info(f"[{kind}] style copied: {dest_sld}")
                    except PermissionError:
                        shutil.copyfile(sld_path, dest_sld)
                        logger.info(f"[{kind}] style copied (no metadata): {dest_sld}")
        
                    ws_prefix = f"{filename}_extended" if kind == "extended" else filename
                    target_publish["data"].append({
                        "workspace": f"{ws_prefix}_{cat_name}",
                        "store_name": f"{ws_prefix}_{cat_name}",
                        "data_path": f"{parts}/output/{data_filename}.{output_format}",
                        "style_name": cat_name,
                        "sld_path": f"{parts}/style/{cat_name}.sld",
                        "write_on_catalogue": True,
                        "description": f"15min analysis - {kind}",
                    })
        
            # ---- CUSTOM → publish MAIN ----
            _publish_styles(
                custom_names,
                poi_category_custom_style,
                kind="custom",
                target_publish=publish_main,
                data_filename=filename,
            )
        
            # ---- extended → publish extended ----
            if has_extended:
                _publish_styles(
                    extended_names,
                    poi_category_extended_style,
                    kind="extended",
                    target_publish=publish_compl,
                    data_filename=f"{filename}_extended",
                )
        
            # ---- scrittura JSON in output/ ----
            os.makedirs(output_dir, exist_ok=True)
            with open(os.path.join(output_dir, "_publish.json"), "w", encoding="utf-8") as f:
                json.dump(publish_main, f, indent=2)
        
            if has_extended:
                with open(os.path.join(f"{output_path_bbox}/extended_poi", "_publish.json"), "w", encoding="utf-8") as f:
                    json.dump(publish_compl, f, indent=2)
        
        return 0


def attach_centroids_to_network(centri, output_path_bbox, mode):
    coefficiente = COEFFICIENT_WALK if mode == 'walk' else COEFFICIENT_BIKE

    nodes = pd.read_csv(f"{output_path_bbox}/osm_network/nodes.csv", index_col=0)
    edges = pd.read_csv(f"{output_path_bbox}/osm_network/edges.csv",
                        index_col=[0, 1]).reset_index()

    nodes_gdf = geopandas.GeoDataFrame(
        nodes,
        geometry=geopandas.points_from_xy(nodes['x'], nodes['y']),
        crs=CRS_4326,
    ).to_crs(CRS_3857)
    nodes['x'] = nodes_gdf.geometry.x
    nodes['y'] = nodes_gdf.geometry.y

    centri = centri.to_crs(CRS_3857)
    tree = cKDTree(np.vstack([nodes['x'], nodes['y']]).T)
    cent_coords = np.vstack([centri.geometry.x, centri.geometry.y]).T
    dist, idx = tree.query(cent_coords, k=1)
    nearest_nodes = nodes.iloc[idx].index.values

    new_nodes = pd.DataFrame({'x': centri.geometry.x, 'y': centri.geometry.y})
    max_node_id = nodes.index.max()
    new_nodes.index = range(max_node_id + 1, max_node_id + 1 + len(new_nodes))
    new_nodes['type'] = 'virtual'

    new_edges = pd.DataFrame({'u': new_nodes.index, 'v': nearest_nodes})
    new_edges['length'] = dist
    new_edges['slope'] = 0
    new_edges['velocita'] = coefficiente * np.exp(
        -3.5 * np.abs(new_edges['slope'] + 0.05)
    ) * (1000 / 60)
    new_edges['time'] = new_edges['length'] / new_edges['velocita']

    reverse_edges = new_edges.rename(columns={'u': 'v', 'v': 'u'})
    new_edges = pd.concat([new_edges, reverse_edges], ignore_index=True)

    nodes_updated = pd.concat([nodes, new_nodes])
    edges_updated = pd.concat([edges, new_edges], ignore_index=True)

    nodes_gdf_updated = geopandas.GeoDataFrame(
        nodes_updated,
        geometry=geopandas.points_from_xy(nodes_updated['x'], nodes_updated['y']),
        crs=CRS_3857,
    )
    nodes_4326 = nodes_gdf_updated.to_crs(CRS_4326)
    nodes_4326['x'] = nodes_4326.geometry.x
    nodes_4326['y'] = nodes_4326.geometry.y

    nodes_to_save = nodes_4326.copy()
    nodes_to_save.index.name = 'id'
    nodes_to_save = nodes_to_save.drop(columns='geometry')
    edges_to_save = edges_updated[['u', 'v', 'length', 'time']]

    nodes_to_save.to_csv(f"{output_path_bbox}/osm_network/nodes.csv")
    edges_to_save.to_csv(f"{output_path_bbox}/osm_network/edges.csv", index=False)
