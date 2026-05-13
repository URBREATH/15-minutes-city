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
from shapely.geometry import Polygon
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

#osm.settings['user_agent'] = "15min-tool contact: chiara.savoldi https://www.dedanext.it/topic-citta-15-minuti/"
headers = {
    "Accept": "application/json",
    "User-Agent": (
        "15min-tool"
        "contact: chiara.savoldi"
    ),
    "Referer": "https://www.dedanext.it/topic-citta-15-minuti/"
}

osmnet.headers = headers

from scripts.storage_minio import upload_on_minio,get_folder,split_path,get_s3_client,minio_file_exists,minio_copy_prefix,minio_list_poi_categories,is_minio_path,split_bucket_and_prefix,load_pois_from_minio
warnings.filterwarnings("ignore")
# Supply the path to the qgis install location:  imposti QGIS per girare senza GUI
#os.environ["QT_QPA_PLATFORM"] = "offscreen"
#QgsApplication.setPrefixPath(r"/opt/conda/envs/geo_indicators/bin/qgis", True)
## QgsApplication.setPrefixPath(r"/opt/conda/envs/geo_indicators/", True)
#gui_flag = False
#app = QgsApplication([], gui_flag)
#app.initQgis()
#
## Inizializza Processing : inizializza il framework Processing di QGIS, che gestisce gli algoritmi (come GDAL, native tools, plugin).
#from processing.core.Processing import Processing
#Processing.initialize()
#
## aggiungi il provider di algoritmi nativi QGIS (buffer, raster, ecc.) al registry Processing.
#
## processing permette di eseguire algoritmi da codice
#import processing
#
#logger.info("QGIS is active!")
#Variabili globali


# GLOBAL
#---------------------

TEMPOMAX = 60 #min
EPSG_3857 = 'EPSG:3857'
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

# area = [lat_min, lon_min, lat_max, lon_max] in EPSG:4326
# lat_meters = length in meters of a vertical linear element located near the bbox (radii, buffers, etc.)
# lat1 = latitude of the bbox (area) center
# lon  = longitude of the bbox (area) center
# (x, y1) = coordinates of the bbox center in EPSG:3003, also representing the first endpoint of the vertical linear working element
# (x, y2) = coordinates of the second endpoint of the vertical linear working element
# lat2 - lat1 = latitude extent (in degrees, EPSG:4326) of the vertical linear working element


def latitudine_gradi(area, lat_metri):
    lat1 = (area[2]+area[0])/2
    lon = (area[3]+area[1])/2
    transformer = Transformer.from_crs(EPSG_4326,EPSG_3857)
    x,y1 = transformer.transform(lat1, lon) #meters
    y2 = y1 + lat_metri #meters
    transformer = Transformer.from_crs(EPSG_3857,EPSG_4326)
    lat2, lon = transformer.transform(x, y2) #gradi
    return((lat2-lat1))
    
def longitudine_gradi(area, lon_metri):
    lon1 = (area[3]+area[1])/2
    lat = (area[2]+area[0])/2
    transformer = Transformer.from_crs(EPSG_4326,EPSG_3857)
    x1,y = transformer.transform(lat, lon1) #meters
    x2 = x1 + lon_metri #meters
    transformer = Transformer.from_crs(EPSG_3857,EPSG_4326)
    lat, lon2 = transformer.transform(x2, y) #gradi
    return((lon2-lon1))


# vale f(0 <= x <= 15) = 1, f(15 < x <= 30) = decade da 1 a 0, f(x > 30) = 0
def decay(time):
    if(time==None): return 0
    elif (time >15 and time <=30): return (-1 * time / 15 + 2)
    elif(time >= 0 and time <=15): return 1
    else: return 0

 
# -----------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------
# BBOX

def create_bbox(bbox, output_path, output_minio_path,hex_diameter_m, access_key, secret_key, endpoint_url):
    if access_key and secret_key and endpoint_url and is_minio_path(output_path):
        
        bucket_name, filepath_minio = split_path(output_minio_path)
        bucket_name, filepath = split_path(output_path)
        minio_copy_prefix(
                        bucket=bucket_name,
                        source_prefix=f"{filepath}/grid/",
                        dest_prefix=f"{filepath_minio}/grid",
                        endpoint_url=endpoint_url,
                        access_key=access_key,
                        secret_key=secret_key
            )
        return 0
              
    grid_folder = os.path.join(output_path, "grid")
    csv_path = f"{grid_folder}/grid_parameter.csv"
    if os.path.exists(grid_folder):
        
        if os.path.exists(grid_folder):
            logger.info(f"The folder {grid_folder} already exists.\n", )
            if access_key and secret_key and endpoint_url: 
                minio_path = os.path.join(output_minio_path, "grid") 
                get_folder(csv_path, minio_path,access_key, secret_key, endpoint_url)
            return 0
        
    else:
        
        latoXCella = 3/2 * hex_diameter_m
        latoYCella = np.sqrt(3)/2 * hex_diameter_m
    
        latitude = latitudine_gradi(bbox, latoYCella)
        longitude = longitudine_gradi(bbox, latoXCella)
    
        riga_bbox = [
            "[" + ",".join([str(el) for el in bbox]) + "]",  # bbox original
            "[" + ",".join([str(el) for el in bbox]) + "]",  # bbox FOR DOWNLOAD
            latitude,
            longitude,
            hex_diameter_m / 2
        ]
        
        os.makedirs(grid_folder)
            
        np.savetxt(csv_path, [riga_bbox], delimiter=';', fmt='%s',
                   header='inputBBox;downloadBBox;latitude;longitude;hex_radius_m', comments='')
         
        if access_key and secret_key and endpoint_url:         
            get_folder(grid_folder, output_minio_path,access_key, secret_key, endpoint_url)
           
        return 0


# -----------------------------------------------------------------------------------------------------------------------------------

# DOWNLOAD

def download(bbox_tassello, output_path_bbox,    
    poi_category_custom_name,
    poi_category_custom_csv,
    poi_category_osm ,
    access_key, 
    secret_key, 
    endpoint_url,
    output_minio_path,
    mode = 'walk',
    weight='time',
    park_gates_source='osm',
    park_gates_osm_buffer_m=10,
    park_gates_csv=None,
    park_gates_virtual_distance_m=100
):
   
    bbox_tassello = json.loads(bbox_tassello)
        
    #Download network 
    download_network_osm(bbox_tassello, output_path_bbox, access_key, secret_key, endpoint_url, output_minio_path, mode, weight)
    
    # Dowload POIs
    download_poi_osm(bbox_tassello, output_path_bbox, poi_category_osm, poi_category_custom_name, poi_category_custom_csv, access_key, secret_key, endpoint_url,output_minio_path,park_gates_source, park_gates_osm_buffer_m
    ,park_gates_csv, park_gates_virtual_distance_m)
           
    return 0


    
def download_poi_osm(
    bbox_tassello,
    output_path_bbox,
    poi_category_osm,
    custom_names,
    custom_csvs,
    access_key, 
    secret_key, 
    endpoint_url,
    output_minio_path,
    park_gates_source='osm',
    park_gates_osm_buffer_m=10,
    park_gates_csv=None,
    park_gates_virtual_distance_m=100
):


    logger.info('DOWNLOAD POIs start.')
    logger.info('----------------------------------------------------------------------------------------------------------------')
        
    
    # Clean inputs
    poi_category_osm = poi_category_osm.strip() if poi_category_osm else None

    logger.info("poi_category_osm: %s", poi_category_osm)
    logger.info("custom_names: %s", custom_names)
    logger.info("custom_csvs: %s", custom_csvs)

    # Folder for POIs
    poi_folder = os.path.join(output_path_bbox, "osm_poi")
    if not os.path.exists(poi_folder):
        os.makedirs(poi_folder)

    # -------------------
    # OSM LOGIC
    # -------------------
            
    if poi_category_osm is not None:
       
        with open("./config/poi_category_osm_tag.json", "r", encoding="utf-8") as f:
            osm_tags = json.load(f)
            valid_poi_category_osm = set(osm_tags.keys())
        
        if poi_category_osm == "all":
            categories_to_download = valid_poi_category_osm
        else:
            categories_to_download = {poi_category_osm.lower()}
        skip_osm_download = False

        if access_key and secret_key and endpoint_url and is_minio_path(output_path_bbox):

            bucket_name, filepath = split_path(output_path_bbox)

            # categorie già presenti su MinIO
            existing_categories = minio_list_poi_categories(
                bucket=bucket_name,
                prefix=f"{filepath}/osm_poi/",
                endpoint_url=endpoint_url,
                access_key=access_key,
                secret_key=secret_key
            )
        
            logger.info(f"POI categories already on MinIO: {existing_categories}")
        
            # scarico SOLO quelle mancanti
            categories_to_download = categories_to_download - existing_categories

            
            bucket_name, filepath_minio = split_path(output_minio_path)

            minio_copy_prefix(
                        bucket=bucket_name,
                        source_prefix=f"{filepath}/osm_poi/",
                        dest_prefix=f"{filepath_minio}/osm_poi",
                        endpoint_url=endpoint_url,
                        access_key=access_key,
                        secret_key=secret_key
            )
                    
            if not categories_to_download:
                logger.info("All requested POI categories already exist on MinIO. Skipping.")
                skip_osm_download = True
            
        if 'park' in categories_to_download and not os.path.isfile(f"{poi_folder}/park.csv"):
            logger.info("Downloading park from OSM and handling park gates...")
            try:
                park_csv_path_local = os.path.join(poi_folder, "park.csv")
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

                    #gates1 = safe_osm_query(bbox_tassello, tags='"barrier"="gate"')
                    #gates2 = safe_osm_query(bbox_tassello, tags='"barrier"="entrance"')
                    #gates3 = safe_osm_query(bbox_tassello, tags='"entrance"="yes"')
                    #gates = pd.concat([gates1, gates2, gates3], ignore_index=True)
                    logger.info('----------------------------------------------------------------------------------------------------------------')                   
                    logger.info(f"Found {len(gates)} park gates from OSM")
                    handle_gates("A", bbox_tassello, output_path_bbox, gates, None, None, park_csv_path_local, park_gates_osm_buffer_m, None)
                    logger.info('----------------------------------------------------------------------------------------------------------------')                    
            
                elif park_gates_source == 'csv' and park_gates_csv:
                    df = pd.read_csv(park_gates_csv)
                    logger.info('----------------------------------------------------------------------------------------------------------------')                    
                    logger.info(f"Loaded {len(df)} park gates from CSV", )
                    df.to_csv(park_csv_path_local, index=False)
                    logger.info('----------------------------------------------------------------------------------------------------------------')                    
            
                elif park_gates_source == 'road_intersect':
            
                    handle_gates("road_intersect", bbox_tassello,output_path_bbox, None, None, None, park_csv_path_local, None, None)
                    logger.info("")
                elif park_gates_source == 'virtual':
                    handle_gates("virtual", bbox_tassello,output_path_bbox, None, None, None, park_csv_path_local, None, park_gates_virtual_distance_m)
                    logger.info("")
            except RuntimeError as e:
                logger.info(e)
                np.savetxt(f"{poi_folder}/park.csv", ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError, requests.exceptions.RequestException) as e:
                logger.info(e)
                pass
                                            
        
        if 'transport' in categories_to_download and not os.path.isfile(f"{poi_folder}/transport.csv"):
        
            tag_dict = osm_tags["transport"]
            dfs = []
        
            for key, values in tag_dict.items():
                values_regex = "|".join(values)
                tags_query = f'"{key}"~"{values_regex}"'
        
                logger.info(f"Downloading transport with tags: {tags_query}")
        
                max_retries = 2
        
                for attempt in range(max_retries):
                    try:
                        df = osm.node_query(
                            bbox_tassello[0],
                            bbox_tassello[1],
                            bbox_tassello[2],
                            bbox_tassello[3],
                            tags=tags_query
                        )
        
                        if df is None or df.empty:
                            df = pd.DataFrame(columns=["id", "lat", "lon"])
        
                        dfs.append(df)
                        break  
        
                    except (HTTPError, requests.exceptions.RequestException) as e:
                        wait = (15 * (attempt + 1)) + random.uniform(3, 8)
                        time.sleep(wait)
        
                    except Exception as e:
                        dfs.append(pd.DataFrame(columns=["id", "lat", "lon"]))
                        break
        
                else:
                    dfs.append(pd.DataFrame(columns=["id", "lat", "lon"]))
        
            time.sleep(15)
        
            if dfs:
                transport = pd.concat(dfs, ignore_index=True)
            else:
                transport = pd.DataFrame(columns=["id", "lat", "lon"])
        
            transport.to_csv(f"{poi_folder}/transport.csv", index=False)
            
             
        for osm_cat in categories_to_download:

            tag_dict = osm_tags[osm_cat]
            dfs = []
            if not os.path.isfile(f"{poi_folder}/{osm_cat}.csv"):        
               
                for key, values in tag_dict.items():
                    values_regex = "|".join(values)
                    tag_query = f'"{key}"~"{values_regex}"'
                            
                    logger.info(f"Downloading {osm_cat} with tags: {tag_query}")
                    max_retries = 2
                    for attempt in range(max_retries):
                        try:
                            df = osm.node_query(
                                bbox_tassello[0],
                                bbox_tassello[1],
                                bbox_tassello[2],
                                bbox_tassello[3],
                                tags=tag_query
                            )
                            if df is None or df.empty:
                                df = pd.DataFrame(columns=["id", "lat", "lon"])
                
                            dfs.append(df)
                            break 
                        except (HTTPError, requests.exceptions.RequestException) as e:
                            wait = (10 * (attempt + 1)) + random.uniform(2,6)
                            time.sleep(wait)
                        except Exception as e:
                            logger.warning(f"node_query failed for {osm_cat} / {tag_query}: {repr(e)}")
                            empty_df = pd.DataFrame(columns=["id", "lat", "lon"])
                            dfs.append(empty_df)
                
                time.sleep(15)                    
                if len(dfs) > 0:
                    result = pd.concat(dfs, ignore_index=True)
                else:
                    result = pd.DataFrame(columns=["id", "lat", "lon"])
                
                result.to_csv(
                    os.path.join(poi_folder, f"{osm_cat}.csv")
                )
            else:
                logger.info(f'Category {osm_cat} csv skipped or already presents.')                        

        if access_key and secret_key and endpoint_url and skip_osm_download is False: 
            get_folder(poi_folder, output_minio_path,access_key, secret_key, endpoint_url)
    # -------------------
    # CUSTOM CSVs
    # -------------------
    if custom_names is not None:
        custom_poi_folder = os.path.join(output_path_bbox, "custom_poi")
        for name, csv_file in zip(custom_names, custom_csvs):
            
            if not os.path.exists(custom_poi_folder):
                os.makedirs(custom_poi_folder)
            csv_path = os.path.join(custom_poi_folder, f"{name}.csv")
            df = pd.read_csv(csv_file)
            logger.info(f"Custom CSV '{csv_file}' has {len(df)} rows")
            df.to_csv(csv_path, index=False)
            logger.info(f"Saved custom CSV as '{name}.csv'")
        if access_key and secret_key and endpoint_url: 
            get_folder(custom_poi_folder, output_minio_path,access_key, secret_key, endpoint_url)
    
    logger.info('----------------------------------------------------------------------------------------------------------------')
    logger.info("DOWNLOAD POIs end.\n")
    return 0



    
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
    
def safe_osm_query(bbox_4326_tassello, tags, pause=15, max_retries=8):

    south, west, north, east = bbox_4326_tassello
    overpass = Overpass()
    
    # costruisci query
    query = f"""
    (
      node({south},{west},{north},{east})[{tags}];
    );
    out geom;
    """

    for attempt in range(max_retries):
        try:
            response = overpass.query(query, timeout=200)
            
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
def handle_gates(gate_source, bbox_tassello, output_path_bbox,  gates, park=None, streets=None, park_csv_path_local=None,park_gates_osm_buffer_m = 10, park_gates_virtual_distance_m = 100):
    
    os.makedirs(os.path.dirname(park_csv_path_local), exist_ok=True)

    """
    Scarica i park da OSM per la bbox e ritorna un GeoDataFrame.
    """
    overpass = Overpass()
    south, west, north, east = bbox_tassello
    south, west, north, east = round(south, 6), round(west, 6), round(north, 6), round(east, 6)

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
            result = overpass.query(query)
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
            streets = download_streets(bbox_tassello)           
            streets = streets.set_crs(EPSG_GATE)
            streets = streets.to_crs(EPSG_METRIC)        
        result_gdf = gates_calculation(park, None, output_path_bbox, park_gates_osm_buffer_m, park_gates_virtual_distance_m, streets, gate_source)
    else:
        result_gdf = gates_calculation(park, None, output_path_bbox,park_gates_osm_buffer_m, park_gates_virtual_distance_m, None, gate_source)
    
    result_gdf.to_csv(park_csv_path_local, index=False)


def download_streets(bbox):
    overpass = Overpass()
    south, west, north, east = bbox
    south, west, north, east = round(south,6), round(west,6), round(north,6), round(east,6)
    # Query Overpass: tutte le way con qualunque valore di 'highway'
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
            result = overpass.query(query)
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


def download_network_osm(bbox_tassello, output_path_bbox,access_key, secret_key, endpoint_url, output_minio_path, mode = 'walk', weight='time'):

          
    if not os.path.exists("{}/osm_network".format(output_path_bbox)):
        os.makedirs("{}/osm_network".format(output_path_bbox))
    local_folder = f"{output_path_bbox}/osm_network"   

    if access_key and secret_key and endpoint_url:

        bucket_name, filepath = split_path(output_path_bbox)
        


        nodes_exists = minio_file_exists(
            bucket=bucket_name,
            object_key=f"{filepath}/osm_network/nodes.csv",
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key
        )
        
        edges_exists = minio_file_exists(
            bucket=bucket_name,
            object_key=f"{filepath}/osm_network/edges.csv",
            endpoint_url=endpoint_url,
            access_key=access_key,
            secret_key=secret_key
        )

        if nodes_exists and edges_exists:
            logger.info("OSM network already exists on MinIO, skipping download.")

            bucket_name, filepath_minio = split_path(output_minio_path)

            minio_copy_prefix(
                        bucket=bucket_name,
                        source_prefix=f"{filepath}/osm_network/",
                        dest_prefix=f"{filepath_minio}/osm_network",
                        endpoint_url=endpoint_url,
                        access_key=access_key,
                        secret_key=secret_key
            )
            return 0

    if not os.path.isfile("{}/osm_network/nodes.csv".format(output_path_bbox)) or not os.path.isfile("{}/osm_network/edges.csv".format(output_path_bbox)):    
        
        logger.info('DOWNLOAD NETWORK start.')
        logger.info('----------------------------------------------------------------------------------------------------------------')
          
        result_get_network, gdf_nodes, gdf_edges = get_network_osm(bbox_tassello, output_path_bbox)
                     
        tassello_nome = os.path.basename(output_path_bbox)
        index = tassello_nome.replace('tassello', '') 
        demPath = f'{output_path_bbox}/merged_dem_{index}.tif'
    
        if weight == 'time':           
           logger.info('Calling the function calculate_edges_time_from_nodes.\n')
           result, gdf_edges  = calculate_edges_time_from_nodes(gdf_edges,  mode = 'walk')

        #Salvo il file nodes
        gdf_nodes['type'] = 'osm'
        gdf_nodes.to_csv("{}/osm_network/nodes.csv".format(output_path_bbox), index = False)     
        #Salvo il file edges
        columns_to_save = ["u", "v", "length", "time"]
        for col in ["time"]:
            if col not in gdf_edges.columns:
                gdf_edges[col] = np.nan
        gdf_edges[columns_to_save].to_csv(f"{output_path_bbox}/osm_network/edges.csv", index=False)
        logger.info('----------------------------------------------------------------------------------------------------------------')     
        logger.info('DOWNLOAD NETWORK end.\n')
    
        
        if access_key and secret_key and endpoint_url: 
            get_folder(local_folder,output_minio_path, access_key, secret_key, endpoint_url)
        
    else:
        logger.info('Files nodes and edges already exists.\n')        
        if access_key and secret_key and endpoint_url: 
            get_folder(local_folder,output_minio_path, access_key, secret_key, endpoint_url)
        return 0
			
	
        
# -----------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------


def get_network_osm(bbox_tassello, output_path_bbox,retries=3,sleep_seconds=1):
    last_exc = None

    for attempt in range(1, retries + 1):
        try:
            logger.info(f"OSM network download attempt {attempt}/{retries}")

            network = osm.pdna_network_from_bbox(
                bbox_tassello[0],
                bbox_tassello[1],
                bbox_tassello[2],
                bbox_tassello[3],
                network_type="walk",
                two_way=False
            )

            # ---------- NODES ----------
            df_nodes = network.nodes_df.reset_index()

            gdf_nodes = geopandas.GeoDataFrame(df_nodes)

            # ---------- EDGES ----------
            df_edges = network.edges_df.reset_index()
            df_edges.rename(
                columns={"from": "u", "to": "v", "distance": "length"},
                inplace=True
            )

            nodes = df_nodes.set_index("id")

            gdf_edges = geopandas.GeoDataFrame(df_edges)
            gdf_edges['geometry'] = df_edges.apply(lambda row: crea_linestring(row, nodes), axis=1)
            logger.info("OSM network successfully downloaded.")
            return 0, gdf_nodes, gdf_edges

        except Exception as e:
            last_exc = e
            logger.warning(f"Attempt {attempt} failed: {e}")

            if attempt < retries:
                time.sleep(sleep_seconds)

    # ------------------------------------------------------------------
    # FALLBACK: network non disponibile → DATAFRAME VALIDI MA VUOTI
    # ------------------------------------------------------------------
    logger.error("All retries failed. Creating empty OSM network.")

    # NODES fallback
    gdf_nodes = geopandas.GeoDataFrame(
        columns=["id", "x", "y", "geometry"],
        geometry="geometry",
        crs=EPSG_4326
    )

    # EDGES fallback
    gdf_edges = geopandas.GeoDataFrame(
        {
            "u": [],
            "v": [],
            "length": [],
            "time": []
        },
        geometry=[],
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
    logger.info(f"Value max of |slope|: {slope_abs.max()}\n")
    logger.info(f"Value min of |slope|: {slope_abs.min()}\n")
    logger.info(f"Value medium of |slope|: {slope_abs.mean()}\n")
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


def walkScore_min(output_path_bbox, poi_category_osm,access_key,secret_key,endpoint_url, output_minio_path, walk_speed_kmh, bike_speed_kmh, mode = 'walk',weight='time'):

        
    if weight == 'time':
        peso = TEMPOMAX
    else:
        if mode == 'walk':
            DISTMAX_FOOT = (walk_speed_kmh / 3.6) * (TEMPOMAX * 60) #meters
            velocita = (walk_speed_kmh / 3.6)
            peso = DISTMAX_FOOT
        else:
            DISTMAX_BIKE = (bike_speed_kmh / 3.6) * (TEMPOMAX * 60) #meters            
            velocita = (bike_speed_kmh / 3.6)
            peso = DISTMAX_BIKE  

    if access_key and secret_key and endpoint_url and is_minio_path(output_path_bbox):
        
        bucket_name, filepath_minio = split_path(output_minio_path)

        s3 = get_s3_client(access_key, secret_key, endpoint_url)
        obj = s3.get_object(
            Bucket=bucket_name,
            Key=f"{filepath_minio}/osm_network/nodes.csv"
        )
        nodes = pd.read_csv(BytesIO(obj["Body"].read()), index_col=0)
        obj = s3.get_object(
            Bucket=bucket_name,
            Key=f"{filepath_minio}/osm_network/edges.csv"
        )
        edges = pd.read_csv(BytesIO(obj["Body"].read()), index_col=[0,1])
        
    else:
        nodes = pd.read_csv("{}/osm_network/nodes.csv".format(output_path_bbox), index_col=0)
        edges = pd.read_csv("{}/osm_network/edges.csv".format(output_path_bbox), index_col=[0,1])
    
   
    edges = edges.reset_index()

    
    if not edges.empty:

        if is_minio_path(output_path_bbox):
            
            pois, list_string = load_pois_from_minio(
                output_path_bbox,
                access_key,
                secret_key,
                endpoint_url
            )

        else:
            
            poi_folder = os.path.join(output_path_bbox, "osm_poi")
            poi_folder_custom = os.path.join(output_path_bbox, "custom_poi")

            # legge automaticamente tutti i csv presenti
            poi_folders = [poi_folder, poi_folder_custom]
            
            csv_files = []
            
            # raccoglie tutti i csv dalle cartelle esistenti
            for folder in poi_folders:
                if os.path.isdir(folder):
                    csv_files.extend(glob.glob(os.path.join(folder, "*.csv")))
            
            csv_files = sorted(csv_files)
            
            list_string = []
            pois = []
            
            for f in csv_files:
                name = os.path.splitext(os.path.basename(f))[0]
                df = pd.read_csv(f)
                list_string.append(name)
                pois.append(df)
        
        logger.info("POIs categories: %s", list_string)


        if weight == 'time':
        
            network = pandana.Network(nodes['x'], nodes['y'], edges['u'], edges['v'], edges[['time']], twoway=False)
        else:
            network = pandana.Network(nodes['x'], nodes['y'], edges['u'], edges['v'], edges[['length']], twoway=False)
           
        walk_score = nodes

        for i in range(0,len(pois)):
            if not pois[i].empty:
                network.set_pois(category = list_string[i], maxdist = peso, maxitems = 1, 
                                x_col = pois[i].lon, y_col = pois[i].lat)
                res = network.nearest_pois(distance = peso, category = list_string[i], num_pois = 1, 
                                        include_poi_ids = False)
                                   
                if weight == 'time':
                    walk_score['minutes_{}'.format(list_string[i])] = res[1]
        
                    
                else:
                    walk_score['minutes_{}'.format(list_string[i])] = res[1] / velocita / 60
                    res = res[1] / velocita / 60
                   
                   
            else: 
                walk_score['minutes_{}'.format(list_string[i])] = 60.0
        walk_score=walk_score.replace({60.0 : None})
        

         
        logger.info('Function walkScore_min completed.\n')
        
        return 0, walk_score    
    else:
        return 0, None


        
#--------------------------------------------------------------------
#-----------------------------------------------------------------       
       
#COMPUTO


def computo(bbox_tassello, latitude, longitude, hex_radius_m , output_path_bbox,custom_names,custom_csvs,grid_gpkg,poi_category_osm, clip_layer, filename,access_key,secret_key,endpoint_url,
 poi_category_custom_style,output_minio_path,virtual_nodes,output_format,output_EPSG, bike_speed_kmh, walk_speed_kmh,mode = 'walk', weight='time'):
            
    bbox = json.loads(bbox_tassello)
    grid_folder = os.path.join(output_path_bbox, "grid")
    if grid_gpkg:
        logger.info(f"Loading existing grid: {grid_gpkg}")
        grid = geopandas.read_file(grid_gpkg)
        if access_key and secret_key and endpoint_url:  
            outputPath_grid = os.path.join(grid_folder, "grid.gpkg")
            grid.to_file(outputPath_grid, driver="GPKG")   
            minio_path = os.path.join(output_minio_path, "grid")             
            get_folder(outputPath_grid, minio_path,access_key, secret_key, endpoint_url)
    else:
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
        transformer = Transformer.from_crs(EPSG_4326,EPSG_3857, always_xy=True)
        xmin,ymin = transformer.transform(bbox[1],bbox[0])
        xmax,ymax = transformer.transform(bbox[3]+1.5*rLon,bbox[2]+np.sqrt(3)/2*rLat)
        boundary_shape = shapely.geometry.box(xmin,ymin,xmax,ymax, ccw=True)
        
        #### ONLY ATHENS
        #boundary_shape = shapely.geometry.box(xmin, ymin, xmax, ymax, ccw=True).buffer(200)
        #
        #try:
        #    region_polys, region_pts = voronoi_regions_from_coords(centri.geometry, boundary_shape)
        #except Exception as e:
        #    logger.info("❌ Errore in voronoi_regions_from_coords:", e)
        #    logger.info("Numero centri:", len(centri))
        #    logger.info("BBox:", bbox)
        #    return 1
        #### ONLY ATHENS
        
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
        
        grid = grid.to_crs(CRS_4326)
        
        grid = grid.drop('index_right', axis = 1)
       

        
        outputPath_grid = os.path.join(grid_folder, 'grid.gpkg')
        grid.to_file(
        outputPath_grid,
        layer="grid",
        driver="GPKG"
        )
        if access_key and secret_key and endpoint_url:  
            minio_path = os.path.join(output_minio_path, "grid") 
            get_folder(outputPath_grid, minio_path,access_key, secret_key, endpoint_url)
            
    # Chiamata della funzione walkScore_min        
    result, walk_score = walkScore_min(output_path_bbox, poi_category_osm,access_key,secret_key,endpoint_url, output_minio_path,walk_speed_kmh, bike_speed_kmh, mode, weight)
    
    if walk_score is None or walk_score.empty:
        ws = []
        result = "{}/{}.csv".format(output_path_bbox, filename)
        np.savetxt(result, ws, delimiter=';', fmt='%s', 
        header = 
        'geometry;overall_average;overall_max', 
        comments='')
        logger.info('The walkScore_min function does not return a ws to work on.')
        if access_key and secret_key and endpoint_url: 
            get_folder(result, output_minio_path,access_key, secret_key, endpoint_url)
        return 0
    else: 
        
    
        walk_score = geopandas.GeoDataFrame(walk_score, geometry = geopandas.points_from_xy(walk_score.x, walk_score.y))
        pois = []
        categories = []
        
        if is_minio_path(output_path_bbox):
            # ------------------------
            # MINIO
            # ------------------------
            pois, categories = load_pois_from_minio(
                output_path_bbox,
                access_key,
                secret_key,
                endpoint_url
            )
        
        else:
            # ------------------------
            # LOCALE
            # ------------------------
            poi_folder = os.path.join(output_path_bbox, "osm_poi")
            custom_poi_folder = os.path.join(output_path_bbox, "custom_poi")
            folders = [poi_folder, custom_poi_folder]
        
            csv_files = []
        
            for folder in folders:
                if os.path.isdir(folder):
                    csv_files.extend(glob.glob(os.path.join(folder, "*.csv")))
        
            csv_files = sorted(csv_files)
        
            for f in csv_files:
                name = os.path.splitext(os.path.basename(f))[0]
                df = pd.read_csv(f)
        
                categories.append(name)
                pois.append(df)
        
        logger.info("POIs categories: %s", categories)

        
               
       # Verify empty hexag
        if virtual_nodes:
            hexag = geopandas.sjoin(grid, walk_score, how='left', predicate = 'contains')

            hexag['missing_categories'] = hexag.apply(
            lambda row: [cat for cat in categories if pd.isna(row.get(f'minutes_{cat}'))],
            axis=1
            )
            # Seleziona solo gli esagoni che hanno almeno una categoria mancante
            empty_hexag = hexag[hexag['missing_categories'].apply(len) > 0].copy()
            centroids_empty_hexag = empty_hexag.copy()
            centroids_empty_hexag['geometry'] = centroids_empty_hexag.geometry.centroid
            
            attach_centroids_to_network(
                centroids_empty_hexag,
                output_path_bbox,
                mode,
                output_minio_path,
                access_key,
                secret_key,
                endpoint_url
            )
            # AGAIN            
            result, walk_score = walkScore_min(output_path_bbox, poi_category_osm,access_key,secret_key,endpoint_url, output_minio_path,walk_speed_kmh, bike_speed_kmh, mode, weight)
            walk_score = geopandas.GeoDataFrame(walk_score, geometry = geopandas.points_from_xy(walk_score.x, walk_score.y))  

       
        hexag = geopandas.sjoin(grid, walk_score, how='inner', predicate = 'contains')
        
        
        hexag = hexag.drop(columns=['highway'], errors='ignore')
        hexag = hexag.drop(columns=['type'], errors='ignore')
        
        hexag = hexag.replace({'NaN' : np.nan})
        
        
        hexag = hexag.dissolve(by = hexag.index, aggfunc="mean")
        

        for cat in categories:
            if 'minutes_{}'.format(cat) not in hexag.columns:
                hexag['minutes_{}'.format(cat)] = np.nan
        if poi_category_osm != 'all':
            for index, row in hexag.iterrows():
                if pd.notnull(row.get('media', np.nan)):
                    hexag.at[index, f'minutes_{poi_category_osm}'] = row['media']
                    
        
        minutes_cols = [f'minutes_{c}' for c in categories]

        hexag['countNaN'] = hexag[minutes_cols].isnull().sum(axis=1)
    
        hexag = hexag[['geometry'] + ['minutes_{}'.format(cat) for cat in categories] + ['countNaN']]
        
        #Calcolo indice continuo (da 0 a 100)
        
        if len(categories) > 1:
            
            hexag['overall_average'] = None
            
            
            for i in hexag.index:
                valori = []
                val100 = []
                num_valori = 0
    
                for j in range(0, len(categories)):
                    val = hexag.at[i,'minutes_{}'.format(categories[j])]
                    
                    if np.isnan(val):
                        valori.append(None)
                    else:
    
                        valori.append(val)
                        num_valori = len(valori)
                    
                    val100.append(decay(val))
                pd.set_option('display.max_columns', None)
                
                if hexag.at[i, 'countNaN'] == len(categories):  # All values are nan
                    hexag.at[i, 'overall_average'] = None
                else:
                    
                    if num_valori > 0:  
                        
                        hexag.at[i, 'overall_average'] = sum(filter(None, valori)) / num_valori  # Calculate the overall_average
                    else:
        
                        hexag.at[i, 'overall_average'] = None  


            def overall_max(row, minutes_cols):
                values = row[minutes_cols]
            
                # Se esiste almeno un NaN → significa "> 60"
                if values.isnull().any():
                    return '>60'
            
                max_val = values.max()
            
                if max_val > 60:
                    return '>60'
            
                return round(max_val, 2)
        
            hexag['overall_max'] = hexag.apply(lambda r: overall_max(r, minutes_cols), axis=1)
        
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
        
        if len(categories) > 1:
            cols_to_keep += ['overall_average', 'overall_max']
        
        # Se clip layer è fornito e valido
        
        if clip_layer and is_minio_path(output_path_bbox):
        
            try:
                bucket_name, clip_key = split_path(clip_layer)
                s3 = get_s3_client(access_key, secret_key, endpoint_url)
                
                obj = s3.get_object(
                    Bucket=bucket_name,
                    Key=clip_key
                )
        

                with tempfile.NamedTemporaryFile(suffix=".gpkg") as tmp:
                    s3.download_fileobj(bucket_name, clip_key, tmp)
                    tmp.flush()
                
                    clip_layer = geopandas.read_file(tmp.name)
                    clip_layer = clip_layer.to_crs(EPSG_METRIC)
                
                hexag_to_save = geopandas.clip(hexag, clip_layer)

        
            except Exception as e:
                logger.warning(f"Clip layer on MinIO not usable: {e}")
                clip_layer = None      
                hexag_to_save = hexag.copy()

            
        elif clip_layer and os.path.isfile(clip_layer) and not is_minio_path(output_path_bbox):
            clip_layer = geopandas.read_file(clip_layer)
            clip_layer = clip_layer.to_crs(EPSG_METRIC)
            hexag_to_save = geopandas.clip(hexag, clip_layer)
        else:
            hexag_to_save = hexag.copy()  # Nessun clipping
        
        
        
        # Mantieni solo le colonne importanti
        hexag_to_save = hexag_to_save[[c for c in cols_to_keep if c in hexag_to_save.columns]]

        output_dir = f"{output_path_bbox}/output"

        # Crea la cartella se non esiste
        os.makedirs(output_dir, exist_ok=True)
        
        hexag_to_save = hexag_to_save.to_crs(f"EPSG:{output_EPSG}")


        if output_format == 'gpkg':
            # Salvataggio GPKG
            hexag_to_save.to_file(
                f"{output_dir}/{filename}.gpkg",
                layer=f"{filename}",
                driver="GPKG"
            )
        elif output_format == "geojson":
            # shapefile = più file (.shp, .dbf, .shx, .prj...) nella stessa cartella
            hexag_to_save.to_file(
                os.path.join(output_dir, f"{filename}.geojson"),
                driver="GeoJSON"
            )
        else:       
            # Salvataggio CSV
            hexag_to_save.to_csv(
                f"{output_dir}/{filename}.csv",
                sep=';', index=False
            )
            
        if access_key and secret_key and endpoint_url: 
            get_folder(output_dir, output_minio_path,access_key, secret_key, endpoint_url)
        
            
            get_folder("style", output_minio_path,access_key, secret_key, endpoint_url)
            parts = output_minio_path.split("/", 1)[1]
            if len(categories) > 1:
                categories.append("overall_average")
                categories.append("overall_max")
            publish_data = {
                    "analysis": "15 minutes city index",
                    "data": []
                    }
            
            for category in categories:
                publish_data["data"].append({
                    "workspace": f"{filename}_{category}",
                    "store_name": f"{filename}_{category}",
                    "data_path": f"{parts}/{filename}.{output_format}",
                    "style_name": f"{category}",
                    "sld_path": f"{parts}/style/{category}.sld",
                    "write_on_catalogue": True,
                    "description": "15min analysis"
                })
            
            if poi_category_custom_style:
                style_name = os.path.splitext(os.path.basename(poi_category_custom_style))[0]
                publish_data["data"].append({
                    "workspace": f"{filename}_{style_name}",
                    "store_name": f"{filename}_{style_name}",
                    "data_path": f"{parts}/{style_name}.{output_format}",
                    "style_name": f"{style_name}",
                    "sld_path": f"{poi_category_custom_style}",
                    "write_on_catalogue": True,
                    "description": "15min analysis"
                })
                
            with open(f"{output_path_bbox}/_publish.json", "w", encoding="utf-8") as f:
                json.dump(publish_data, f, indent=2)
                                    
            get_folder(f"{output_path_bbox}/_publish.json", output_minio_path,access_key, secret_key, endpoint_url)
            
        return 0

                   





def attach_centroids_to_network(centri, output_path_bbox, mode,output_minio_path, access_key,
                secret_key,
                endpoint_url):
    
    # --- 1. Leggi rete ---
    if mode == 'walk':
        coefficiente = COEFFICIENT_WALK
    else:
        coefficiente = COEFFICIENT_BIKE
    

    if access_key and secret_key and endpoint_url and is_minio_path(output_path_bbox):
        
        bucket_name, filepath_minio = split_path(output_minio_path)

        s3 = get_s3_client(access_key, secret_key, endpoint_url)
        obj = s3.get_object(
            Bucket=bucket_name,
            Key=f"{filepath_minio}/osm_network/nodes.csv"
        )
        nodes = pd.read_csv(BytesIO(obj["Body"].read()), index_col=0)
        obj = s3.get_object(
            Bucket=bucket_name,
            Key=f"{filepath_minio}/osm_network/edges.csv"
        )
        #edges = pd.read_csv(BytesIO(obj["Body"].read()), index_col=[0,1])
        edges = pd.read_csv(BytesIO(obj["Body"].read()))
    else:
        nodes = pd.read_csv(f"{output_path_bbox}/osm_network/nodes.csv", index_col=0)
        edges = pd.read_csv(f"{output_path_bbox}/osm_network/edges.csv", index_col=[0,1]).reset_index()
        
    

    # converti nodes in GeoDataFrame
    nodes_gdf = geopandas.GeoDataFrame(
        nodes,
        geometry=geopandas.points_from_xy(nodes['x'], nodes['y']),
        crs=CRS_4326
    )
    
    # trasformazione in metri
    nodes_gdf = nodes_gdf.to_crs(CRS_3857)
    
    # aggiorna x e y
    nodes['x'] = nodes_gdf.geometry.x
    nodes['y'] = nodes_gdf.geometry.y

    

    # (deve essere in metri!)
    centri = centri.to_crs(CRS_3857)

    #np.vstack([...]) → li mette uno sopra l’altro
    # .T → trasposta    
    # [[x1, y1],
    # [x2, y2],
    # [x3, y3],
    # ...]
    
    # --- 3. KDTree sui nodi ---
    node_coords = np.vstack([nodes['x'], nodes['y']]).T
    
    # organizza questi punti in modo che io possa trovare i vicini velocemente
    tree = cKDTree(node_coords)

    # --- 4. Coordinate centroidi ---
    cent_coords = np.vstack([centri.geometry.x, centri.geometry.y]).T

    # per ogni centroide trova il nodo piu vicino
    # dist = distanza tra centroide e nodo
    #idx = posizione del nodo più vicino ( nel dataframe)
    
    dist, idx = tree.query(cent_coords, k=1)
    
    # prende le righe dei nodi trovati
    #estrae il loro index (node_id reale) 

    nearest_nodes = nodes.iloc[idx].index.values

    # --- 6. Crea nuovi nodi: prende i centroidi degli esagoni ---
    new_nodes = pd.DataFrame({
        'x': centri.geometry.x,
        'y': centri.geometry.y
    })
    
    # Trova l’ID più alto tra i nodi esistenti
    max_node_id = nodes.index.max()
    # Assegna ID nuovi ai centroidi
    new_nodes.index = range(max_node_id + 1, max_node_id + 1 + len(new_nodes))
    new_nodes['type'] = 'virtual'
    
    # --- 7. Crea archi: centroide → nodo OSM più vicino ---
    new_edges = pd.DataFrame({
        'u': new_nodes.index,
        'v': nearest_nodes
    })

    # --- 8. Calcolo lunghezza e tempo: assegna la distanza ---
    new_edges['length'] = dist
    new_edges['slope'] = 0  

    # velocità con modello
    new_edges['velocita'] = coefficiente * np.exp(
        -3.5 * np.abs(new_edges['slope'] + 0.05)
    ) * (1000 / 60)
    
    # tempo corretto
    new_edges['time'] = new_edges['length'] / new_edges['velocita']


    # --- 9. Rendi bidirezionale ---
    # prima:  centroide → nodo
    # dopo:   nodo → centroide
    reverse_edges = new_edges.rename(columns={'u': 'v', 'v': 'u'})
    new_edges = pd.concat([new_edges, reverse_edges], ignore_index=True)



    # --- 10. Aggiorna rete ---
    # aggiunge i nuovi nodi  e archi  alla rete
    nodes_updated = pd.concat([nodes, new_nodes])
    edges_updated = pd.concat([edges, new_edges], ignore_index=True)
    
    
    nodes_gdf_updated = geopandas.GeoDataFrame(
        nodes_updated,
        geometry=geopandas.points_from_xy(nodes_updated['x'], nodes_updated['y']),
        crs=CRS_3857
    )
    
    nodes_4326 = nodes_gdf_updated.to_crs(CRS_4326)
    nodes_4326['x'] = nodes_4326.geometry.x
    nodes_4326['y'] = nodes_4326.geometry.y

    nodes_to_save = nodes_4326.copy()
    nodes_to_save.index.name = 'id'
    nodes_to_save = nodes_to_save.drop(columns='geometry')
    edges_to_save = edges_updated[['u', 'v', 'length', 'time']]
    logger.info(f"edges dtypes:\n{edges_updated[['u','v','length','time']].dtypes}")

    if access_key and secret_key and endpoint_url and is_minio_path(output_path_bbox):
        bucket_name, base_prefix = split_path(output_minio_path)
    
        s3 = get_s3_client(access_key, secret_key, endpoint_url)
    
        nodes_key = f"{base_prefix}/osm_network/nodes.csv"
        edges_key = f"{base_prefix}/osm_network/edges.csv"
    
        # nodes.csv (con index)
        buf_nodes = BytesIO()
        nodes_to_save.to_csv(buf_nodes)  # mantiene index
        buf_nodes.seek(0)
        s3.put_object(
            Bucket=bucket_name,
            Key=nodes_key,
            Body=buf_nodes.getvalue(),
            ContentType="text/csv"
        )
    
        # edges.csv (senza index)
        buf_edges = BytesIO()
        edges_to_save.to_csv(buf_edges, index=False)
        buf_edges.seek(0)
        s3.put_object(
            Bucket=bucket_name,
            Key=edges_key,
            Body=buf_edges.getvalue(),
            ContentType="text/csv"
        )
    
    else:
        nodes_to_save.to_csv(
            f"{output_path_bbox}/osm_network/nodes.csv"
        )
        
        
        edges_to_save.to_csv(
            f"{output_path_bbox}/osm_network/edges.csv",
            index=False
        )
