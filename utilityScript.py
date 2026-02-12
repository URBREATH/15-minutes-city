    #IMPORT
#---------------
import geopandas
import numpy as np
import pandas as pd
from enum import Enum
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
from osgeo import gdal
import zipfile
import rasterio
from geovoronoi import voronoi_regions_from_coords, points_to_coords
from shapely import wkt
from urllib.error import HTTPError
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
from rasterio.env import Env
import subprocess
import math
import urllib3
import warnings
from shapely.ops import transform
from shapely import wkt
from pyproj import Proj, transform
import ast
from shapely.geometry import Polygon
from gates_green_areas import Gates_green_areas
from qgis.core import *  # Include tutto da qgis.core
from qgis.analysis import QgsNativeAlgorithms
from qgis.PyQt.QtCore import QVariant
import processing
from requests.exceptions import HTTPError
from qgis.utils import plugins
from OSMPythonTools.overpass import Overpass, overpassQueryBuilder


# Supply the path to the qgis install location:  imposti QGIS per girare senza GUI
os.environ["QT_QPA_PLATFORM"] = "offscreen"
QgsApplication.setPrefixPath(r"/opt/conda/envs/geo_indicators/bin/qgis", True)
# QgsApplication.setPrefixPath(r"/opt/conda/envs/geo_indicators/", True)
gui_flag = False
app = QgsApplication([], gui_flag)
app.initQgis()

# Inizializza Processing : inizializza il framework Processing di QGIS, che gestisce gli algoritmi (come GDAL, native tools, plugin).
from processing.core.Processing import Processing
Processing.initialize()

# aggiungi il provider di algoritmi nativi QGIS (buffer, raster, ecc.) al registry Processing.

# processing permette di eseguire algoritmi da codice
import processing

print("QGIS is active!")
#Variabili globali

class PostDownloadMode(Enum):
    AS_IS = 0
    ONLY_A = 1
    A_B_C = 2
    
# GLOBAL
#---------------------

TEMPOMAX = 60 #min
TILE_SIZE = 10000 #meters
CONSTANT_SIZE = 50000 #meters
BIKE_VEHICLE_SPEED = 15 # km/h
FOOT_SPEED = 5 # km/h
EPSG_3857 = 'EPSG:3857'
CRS_3857 = 3857
EPSG_4326 = 'EPSG:4326'
CRS_4326 = 4326
EPSG_32632 = 'EPSG:32632'
EPSG_GATE = 'EPSG:4326'
EPSG_METRIC = 'EPSG:3857'
COEFFICIENT_FOOT = 6 #km/h
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

def create_unique_bbox(bbox, outputPath, category='all', by='foot'):
    try:
        if os.path.exists(outputPath):
            print("The folder already exists.\n", flush=True)
            return 0
        else:
            diam = 250
            latoXCella = 3/2 * diam
            latoYCella = np.sqrt(3)/2 * diam

            latCella = latitudine_gradi(bbox, latoYCella)
            lonCella = longitudine_gradi(bbox, latoXCella)

            riga_bbox = [
                "[" + ",".join([str(el) for el in bbox]) + "]",  # bbox original
                "[" + ",".join([str(el) for el in bbox]) + "]",  # bbox FOR DOWNLOAD
                latCella,
                lonCella,
                diam / 2
            ]
            
            os.makedirs(outputPath)

            csv_path = f"{outputPath}/unique_bbox.csv"
            np.savetxt(csv_path, [riga_bbox], delimiter=';', fmt='%s',
                       header='ComputoBBox;downloadBBox;latCella;lonCella;raggio', comments='')

            
            return 0
    except Exception as e:
        print(f"Error while creating the bbox: {e}.\n", flush=True)

# -----------------------------------------------------------------------------------------------------------------------------------

# DOWNLOAD

def download(bbox_tassello, outputPath_bbox, category = 'all', by='foot', weight='time', flag_or = True, flag_post_download= PostDownloadMode.ONLY_A, gate_path=None):
   
   # Only in this function return = 0 (failure) and return = 1 (success) !!!!!
    success = 1 
    failure = 0
    try:
        bbox_tassello = json.loads(bbox_tassello)


        #Download network 
        if download_network_osm(bbox_tassello, outputPath_bbox,  by, weight) == 1:
            return failure
    
        
        if download_poi_osm(bbox_tassello, outputPath_bbox, category, flag_or, flag_post_download, gate_path) == 1:
            return failure
               
        return success
        
    except Exception as e: 
        print(f"Error dowload function: {e}.\n", flush=True)

def download_poi_osm(bbox_tassello, outputPath_bbox, category = 'all', flag_or = True, flag_post_download= PostDownloadMode.ONLY_A, gate_path=None):
  
    try:
        print('DOWNLOAD POIs start.', flush = True)
        print('----------------------------------------------------------------------------------------------------------------', flush = True)
        
        if not os.path.exists(outputPath_bbox):
            print(f"Error: The folder {outputPath_bbox} doesn't exist.\n")
            return 1 
        
        categorie_valide = {'restaurantcafe', 'shop', 'postbank', 'park', 'health', 'marketgroc', 'entertainment', 'education', 'all'}
    
        if category not in categorie_valide:
            print(f"Error: Category '{category}' not valid. Choose between {', '.join(categorie_valide)}.")
            return 1
            
        if not os.path.exists("{}/poi".format(outputPath_bbox)):
            os.makedirs("{}/poi".format(outputPath_bbox))
            
        if not os.path.isfile("{}/poi/restaurantcafe.csv".format(outputPath_bbox)) and (category=='restaurantcafe' or category=='all'):
            try:
                restaurantcafe = osm.node_query(bbox_tassello[0], bbox_tassello[1], bbox_tassello[2],bbox_tassello[3], 
                                      tags='"amenity"~"restaurant|pub|bar|cafe|fast_food|food_court|ice_cream|biergarden"')
                #restaurantcafe = restaurantcafe[['lon','lat']]
                restaurantcafe.to_csv("{}/poi/restaurantcafe.csv".format(outputPath_bbox))
            except RuntimeError as e:
                print(e, flush=True)
                np.savetxt("{}/poi/restaurantcafe.csv".format(outputPath_bbox), ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError,requests.exceptions.RequestException) as e: 
                print(e, flush=True)
                pass
        
        if not os.path.isfile("{}/poi/education.csv".format(outputPath_bbox)) and (category=='education' or category=='all'):
            try:
                education = osm.node_query(bbox_tassello[0], bbox_tassello[1], bbox_tassello[2],bbox_tassello[3], 
                                     tags='"amenity"~"college|driving_school|kindergarten|language_school|music_school|school|university"')
                #education = education[['lon','lat']]
                education.to_csv("{}/poi/education.csv".format(outputPath_bbox))
            except RuntimeError as e:
                print(e, flush=True)
                np.savetxt("{}/poi/education.csv".format(outputPath_bbox), ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError,requests.exceptions.RequestException) as e: 
                print(e, flush=True)
                pass
        
        if not os.path.isfile("{}/poi/marketgroc.csv".format(outputPath_bbox)) and (category=='marketgroc' or category=='all'):
            try:
                marketgroc = osm.node_query(bbox_tassello[0], bbox_tassello[1], bbox_tassello[2],bbox_tassello[3], 
                                      tags='"shop"~"alcohol|bakery|beverages|brewing_supplies|butcher|cheese|chocolate|coffee|confectionery|convenience|deli|dairy|farm|frozen_food|greenmarketgrocer|health_food|ice_cream|pasta|pastry|seafood|spices|tea|water|supermarket|department_store|general|kiosk|mall"')
                #marketgroc = marketgroc[['lon','lat']]
                marketgroc.to_csv("{}/poi/marketgroc.csv".format(outputPath_bbox))            
            except RuntimeError as e:
                print(e, flush=True)
                np.savetxt("{}/poi/marketgroc.csv".format(outputPath_bbox), ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError,requests.exceptions.RequestException) as e: 
                print(e, flush=True)
                pass
        
        if not os.path.isfile("{}/poi/postbank.csv".format(outputPath_bbox)) and (category=='postbank' or category=='all'):   
            try:
                postbank = osm.node_query(bbox_tassello[0], bbox_tassello[1], bbox_tassello[2],bbox_tassello[3], 
                                       tags = '"amenity"~"atm|bank|bureau_de_change|post_office"')
                #postbank = postbank[['lon','lat']]
                postbank.to_csv("{}/poi/postbank.csv".format(outputPath_bbox))   
            except RuntimeError as e:
                print(e, flush=True)
                np.savetxt("{}/poi/postbank.csv".format(outputPath_bbox), ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError,requests.exceptions.RequestException) as e: 
                print(e, flush=True)
                pass
        
        if not os.path.isfile("{}/poi/park.csv".format(outputPath_bbox)) and (category=='park' or category=='all'):    
            try:
               
                if flag_or:
                    print("Uso i gate forniti dall’esterno")
                    if gate_path is None:
                        print('Devi fornire il path dei gates', flush=True)
                        return 1
                    
                    gates  = gate_path  


                    if flag_post_download.name == "AS_IS":
                        print("Uso i gate così come sono")
                        #Semplicemente li salvo
                        if os.path.exists(gates):
                            gates_df = pd.read_csv(gates)
                            gates_df.to_csv(f"{outputPath_bbox}/poi/park.csv", sep=',', index=False)
                        else:
                            np.savetxt(f"{outputPath_bbox}/poi/park.csv",
                                    ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
                    
                    #Se ho i gate forniti dall'esterno ma li voglio di tipo A o B/C. Ho gia i gate
                    #scarico le aree verdi e li filtro.
                    elif flag_post_download.name in ("ONLY_A", "A_B_C"):
                        print(f"Calcolo i gate di tipo {flag_post_download.name}")
                        gates_df = pd.read_csv(gates)
                        # park e streets in questo caso li avresti già caricati da file esterni se necessario
                        csv_path = os.path.join(outputPath_bbox, "poi", "park.csv")
                     
                        handle_gates(flag_post_download,bbox_tassello, gates_df, None, None, csv_path)
                
                else:
                    print("Scarico i gate da OSM")
                    gates1 = safe_osm_query(bbox_tassello, tags = '"barrier"~"gate|entrance"')
                    gates2 = safe_osm_query(bbox_tassello, tags='"entrance"~"yes"')
                    gates = pd.concat([gates1, gates2], ignore_index=True)
                    
                    if flag_post_download.name == "AS_IS":
                        print("Uso i gate così come sono")
                        gates.to_csv(f"{outputPath_bbox}/poi/park.csv")
                    
                    elif flag_post_download.name in ("ONLY_A", "A_B_C"):
                        print(f"Calcolo i gate di tipo {flag_post_download.name}")
                        
                        csv_path = os.path.join(outputPath_bbox, "poi", "park.csv")
                        handle_gates(flag_post_download,bbox_tassello, gates, None, None, csv_path)
                    

            except RuntimeError as e:
                print(e, flush=True)
                np.savetxt("{}/poi/park.csv".format(outputPath_bbox, category), ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError,requests.exceptions.RequestException) as e: 
                print(e, flush=True)
                pass
        
        if not os.path.isfile("{}/poi/entertainment.csv".format(outputPath_bbox)) and (category=='entertainment' or category=='all'):
            try:
                entertainment = osm.node_query(bbox_tassello[0], bbox_tassello[1], bbox_tassello[2],bbox_tassello[3], 
                                     tags = '"amenity"~"arts_centre|brothel|casino|cinema|community_centre|conference_centre|events_venue|fountain|gambling|love_hotel|nightclub|planetarium|public_bookcase|social_centre|stripclub|studio|swingerclub|theatre"')
                #entertainment = entertainment[['lon','lat']]
                entertainment.to_csv("{}/poi/entertainment.csv".format(outputPath_bbox))    
            except RuntimeError as e:
                print(e, flush=True)
                np.savetxt("{}/poi/entertainment.csv".format(outputPath_bbox), ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError,requests.exceptions.RequestException) as e: 
                print(e, flush=True)
                pass
        
        if not os.path.isfile("{}/poi/shop.csv".format(outputPath_bbox)) and (category=='shop' or category=='all'):
            try:
                shop = osm.node_query(bbox_tassello[0], bbox_tassello[1], bbox_tassello[2],bbox_tassello[3], 
                                       tags='"shop"~"department_store|general|kiosk|mall|wholesale|baby_goods|bag|boutique|clothes|fabric|fashion_accessories|jewelry|leather|watches|wool|charity|second_hand|variety_store|beauty|chemist|cosmetics|erotic|hairdresser|hairdresser_supply|hearing_aids|herbalist|massage|medical_supply|nutrition_supplements|optician|perfumery|tattoo|agrarian|appliance|bathroom_furnishing|doityourself|electrical|energy|fireplace|florist|garden_centre|garden_furniture|gas|glaziery|groundskeeping|hardware|houseware|locksmith|paint|security|trade|antiques|bed|candles|carpet|curtain|doors|flooring|furniture|household_linen|interior_decoration|kitchen|lighting|tiles|window_blind|computer|electronics|hifi|mobile_phone|radiotechnics|vacuum_cleaner|atv|bicycle|boat|car|car_repair|car_parts|caravan|fuel|fishing|golf|hunting|jetski|military_surplus|motorcycle|outdoor|scuba_diving|ski|snowmobile|swimming_pool|trailer|tyres|art|collector|craft|frame|games|model|music|musical_instrument|photo|camera|trophy|video|video_games|anime|books|gift|lottery|newsagent|stationery|ticket|bookmaker|cannabis|copynode|dry_cleaning|e-cigarette|funeral_directors|laundry|money_lender|party|pawnbroker|pet|pet_grooming|pest_control|pyrotechnics|religion|storage_rental|tobacco|toys|travel_agency|vacant|weapons|outpost"')
                #shop = shop[['lon','lat']]
                shop.to_csv("{}/poi/shop.csv".format(outputPath_bbox)) 
            except RuntimeError as e:
                print(e, flush=True)
                np.savetxt("{}/poi/shop.csv".format(outputPath_bbox), ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError,requests.exceptions.RequestException) as e: 
                print(e, flush=True)
                pass
        
        if not os.path.isfile("{}/poi/health.csv".format(outputPath_bbox)) and category=='all':
            try:
                health = osm.node_query(bbox_tassello[0], bbox_tassello[1], bbox_tassello[2],bbox_tassello[3], 
                                      tags='"amenity"~"clinic|dentist|doctors|hospital|nursing_home|pharmacy|social_facility"')
                #health = health[['lon','lat']]
                health.to_csv("{}/poi/health.csv".format(outputPath_bbox)) 
            except RuntimeError as e:
                print(e, flush=True)
                np.savetxt("{}/poi/health.csv".format(outputPath_bbox), ['id,lat,lon,amenity'], delimiter=';', fmt='%s')
            except (HTTPError,requests.exceptions.RequestException) as e: 
                print(e, flush=True)
                pass
        print('----------------------------------------------------------------------------------------------------------------', flush = True)     
        print("DOWNLOAD POIs end.\n")         
        if category == 'all':
            files = next(os.walk("{}/poi".format(outputPath_bbox)))[2] + next(os.walk("{}/network".format(outputPath_bbox)))[2]

            if(len(files)) == 10: return(0)
            else: return(1)
        else:
            if not os.path.isfile("{}/poi/{}.csv".format(outputPath_bbox, category)):
                return(1)
            else: return(0)
			
    except Exception as e:
        print(f"Error during download_poi_osm: {e}.\n", flush = True)
    
def gates_calculation(park_gdf, gates_df, streets=None, gates_type='A', outputPath_tassello="."):
    try:
        
        
        # Copia dei gates
        gates_df = gates_df.copy()

        # Rimuove lat/lon mancanti
        gates_df = gates_df.dropna(subset=['lat', 'lon'])
        gates_df['geometry'] = geopandas.points_from_xy(gates_df['lon'], gates_df['lat'])

        # Trasforma in GeoDataFrame con CRS coerente
        gates_gdf = geopandas.GeoDataFrame(gates_df, geometry=geopandas.points_from_xy(gates_df['lon'], gates_df['lat']), crs="EPSG:4326")
        gates_gdf = gates_gdf.to_crs(EPSG_METRIC)

        # Assicura ID univoci
        if 'id' in gates_gdf.columns:
            gates_gdf['id'] = pd.factorize(gates_gdf['id'])[0] + 1
        
        gates_gdf = gates_gdf.reset_index(drop=True)
        # Filtra solo geometrie valide
        gates_gdf = gates_gdf[gates_gdf['geometry'].notna()]
        if 'fid' not in park_gdf.columns:
            park_gdf = park_gdf.copy()
            park_gdf['fid'] = range(1, len(park_gdf) + 1)
        
        if 'fid' not in gates_gdf.columns:
            gates_gdf = gates_gdf.copy()
            gates_gdf['fid'] = range(1, len(gates_gdf) + 1)
        
        if streets is not None and 'fid' not in streets.columns:
            streets = streets.copy()
            streets['fid'] = range(1, len(streets) + 1)

        temp_gpkg = os.path.join(outputPath_tassello, "temp_gates.gpkg")
        gates_gdf.to_file(temp_gpkg, layer='gate_osm', driver='GPKG')
        # Creazione layer QGIS
        park_layer = QgsVectorLayer(park_gdf.to_json(), "green_areas", "ogr")
        gates_layer = QgsVectorLayer(f"{temp_gpkg}|layername=gate_osm", "gate_osm", "ogr")
        

        for lyr, name in [(park_layer, "green_areas"), (gates_layer, "gate_osm")]:
            if not lyr.isValid():
                raise ValueError(f"Il layer '{name}' non è valido!")
            else:
                print(f"Layer '{name}' valido con {lyr.featureCount()} feature.")
        alg = Gates_green_areas()
        # Algoritmo di calcolo gate

        if gates_type == 'A':
            
            output_gpkg = os.path.join(outputPath_tassello, "gatesA.gpkg")
            params = {
            'mode': 'A',
            'green_areas': park_layer,
            'gate_osm': gates_layer,
            'streets': None,   # non serve in modalità A
            'Gates': output_gpkg
            }
        else:  # tipo B/C o ABC
            if streets is None:
                raise ValueError("Per i gate di tipo B/C, il layer streets è necessario.")
            output_gpkg = os.path.join(outputPath_tassello, "gatesABC.gpkg")

            streets_layer = QgsVectorLayer(streets.to_json(), "streets", "ogr")
            if not streets_layer.isValid():
                raise ValueError("Il layer 'streets' non è valido!")
            print(f"Layer 'streets' valido con {streets_layer.featureCount()} feature.")
            params = {
                'mode': 'ABC', 
                'green_areas': park_layer,
                'gate_osm': gates_layer,
                'streets': streets_layer,
                'Gates': output_gpkg
            }

        # Contesto QGIS
        context = QgsProcessingContext()
        feedback = QgsProcessingFeedback()
        results = alg.processAlgorithm(params, context, feedback)

        # Lettura output

        print("Output salvato in GPKG:", results['Gates'])
        return geopandas.read_file(results['Gates'])


    except Exception as e:
        print(f"Errore durante gates_calculation: {e}", flush=True)
        return None

# ------------------------------------------------------------
# Funzione per evitare troppe richieste OSM
# ------------------------------------------------------------
def safe_osm_query(bbox, tags, pause=1, max_retries=3):
    for attempt in range(max_retries):
        try:
            df = osm.node_query(*bbox, tags=tags)
            time.sleep(pause)
            if df is None or df.empty:
                return pd.DataFrame(columns=['id','lat','lon','amenity'])
            return df
        except Exception as e:
            print(f"Errore nella query {tags}: {e} (tentativo {attempt+1}/{max_retries})")
            time.sleep(pause*2)
    return pd.DataFrame(columns=['id','lat','lon','amenity'])

# ------------------------------------------------------------
# Gestione completa dei gates
# ------------------------------------------------------------
def handle_gates(flag_post_download, bbox_tassello, gates, park=None, streets=None, csv_path=None):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    # park e streets solo se necessario
    # I park sono polygon
    if park is None:
        overpass = Overpass()
        north, south, east, west = bbox_tassello
        
        query = overpassQueryBuilder(
            bbox=(north, south, east, west),
            elementType=['way','relation'],
            selector='"leisure"~"park|dog_park"',
            includeGeometry=True
        )
        
        result = overpass.query(query)
        data = []
        
        for el in result.elements():
           try:
            geom = el.geometry()
            if geom:
             data.append({'id': el.id(), 'amenity': el.tag('leisure'), 'geometry': shapely.geometry.shape(geom)})
           except Exception as e:
            print(f"Attenzione: relazione {el.id()} ignorata perché geometria non valida: {e}")
        
        park = geopandas.GeoDataFrame(data, geometry='geometry', crs=EPSG_GATE)
        park = park.to_crs(EPSG_METRIC)
        #park = park[park.geometry.notna() & park.geometry.is_valid]
        #park = park[park.geometry.type.isin(['Polygon', 'MultiPolygon'])]

    if flag_post_download.name == "ONLY_A":
        
        result_gdf = gates_calculation(park, gates, None, 'A')
    elif flag_post_download.name == "A_B_C":
        if streets is None:

            streets = download_streets(bbox_tassello)
            
           
            streets = streets.set_crs(EPSG_GATE)
            streets = streets.to_crs(EPSG_METRIC)
        
        result_gdf = gates_calculation(park, gates, streets, 'ABC')
    else:
        result_gdf = None
    print('The result', result_gdf)
    if result_gdf is not None and not result_gdf.empty:
        print('csv_path', csv_path)
        result_gdf.to_csv(csv_path, index=False)
    else:
        print("Errore nella generazione dei gate, CSV vuoto salvato")
        pd.DataFrame(columns=['id','lat','lon','amenity']).to_csv(csv_path, index=False, sep=';')



def download_streets(bbox):
    overpass = Overpass()
    south, west, north, east = bbox
    south, west, north, east = round(south,6), round(west,6), round(north,6), round(east,6)

    # Query Overpass: tutte le way con qualunque valore di 'highway'
    query = f"""
    (
      way({south},{west},{north},{east})[highway];
    );
    out geom;
    """

    try:
        result = overpass.query(query)
    except Exception as e:
        print(f"Errore download strade: {e}")
        return geopandas.GeoDataFrame(columns=["id","highway","geometry"], geometry="geometry")

    data = []

    for el in result.elements():
        geom = el.geometry()
        if geom:
            shape = shapely.geometry.shape(geom)
            if shape.geom_type in ["LineString", "MultiLineString"]:
                data.append({
                    "id": el.id(),
                    "highway": el.tag("highway"),
                    "geometry": shape
                })

    if data:
        return geopandas.GeoDataFrame(data, geometry="geometry")
    else:
        return geopandas.GeoDataFrame(columns=["id","highway","geometry"], geometry="geometry")



# -----------------------------------------------------------------------------------------------------------------------------------
           
def download_network_osm(bbox_tassello, outputPath_bbox,  by='foot', weight='time'):
    try:
		

        if not os.path.exists(outputPath_bbox):
            print(f"Error: The folder {outputPath_bbox} doesn't exist.\n")
            return 1
          
        if not os.path.exists("{}/network".format(outputPath_bbox)):
            os.makedirs("{}/network".format(outputPath_bbox))
            
    
        if not os.path.isfile("{}/network/nodes.csv".format(outputPath_bbox)) or not os.path.isfile("{}/network/edges.csv".format(outputPath_bbox)):    
            
            print('DOWNLOAD NETWORK start.', flush = True)
            print('----------------------------------------------------------------------------------------------------------------', flush = True)
              
            result_get_network, gdf_nodes, gdf_edges = get_network_osm(bbox_tassello, outputPath_bbox)
                         
            if  result_get_network == 1:
                print('Problem in recovering the road network.\n', flush = True)
                np.savetxt("{}/network/nodes.csv".format(outputPath_bbox), ['id,x,y'], delimiter=';', fmt='%s')
                np.savetxt("{}/network/edges.csv".format(outputPath_bbox), ['u,v,length,time'], delimiter=';', fmt='%s')
                return 0
            tassello_nome = os.path.basename(outputPath_bbox)
            index = tassello_nome.replace('tassello', '') 
            demPath = f'{outputPath_bbox}/merged_dem_{index}.tif'

            if weight == 'time':           
               print('Calling the function calculate_edges_time_from_nodes.\n', flush =True)
               result, gdf_edges  = calculate_edges_time_from_nodes(gdf_edges,  by='foot')
               if  result == 1:
                   print('Problem saving the edges file.\n', flush = True)                 
                   return 1
            #Salvo il file nodes
            gdf_nodes.to_csv("{}/network/nodes.csv".format(outputPath_bbox), index = False)     
            #Salvo il file edges
            columns_to_save = ["u", "v", "length", "time"]
            for col in ["time"]:
                if col not in gdf_edges.columns:
                    gdf_edges[col] = np.nan
            gdf_edges[columns_to_save].to_csv(f"{outputPath_bbox}/network/edges.csv", index=False)
            print('----------------------------------------------------------------------------------------------------------------', flush = True)     
            print('DOWNLOAD NETWORK end.\n', flush = True)
            
            return 0
        else:
            print('Files nodes and edges already exists.\n', flush = True)
            return 0
			
    #except (HTTPError,requests.exceptions.RequestException) as e: 
    #    print(e, flush=True)
    #    pass
	
    except Exception as e:
        np.savetxt("{}/network/nodes.csv".format(outputPath_bbox), ['id,x,y'], delimiter=';', fmt='%s')
        np.savetxt("{}/network/edges.csv".format(outputPath_bbox), ['u,v,length,time'], delimiter=';', fmt='%s')
        print(f"Error during the download_network_osm: {e}.\n", flush = True)
        return 1
        
        
# -----------------------------------------------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------------------------------------------
# GET NETWORK OSM FUNCTION

def get_network_osm(bbox_tassello, outputPath_bbox):
    try:
		
        if not os.path.exists(outputPath_bbox):
            print(f"Error: The folder {outputPath_bbox} doesn't exist.\n")
            return 1, None, None
        network = osm.pdna_network_from_bbox(bbox_tassello[0], bbox_tassello[1], bbox_tassello[2],bbox_tassello[3], network_type='walk', two_way = False)
        df_edges = network.edges_df.reset_index()
        df_nodes = network.nodes_df.reset_index()
        df_edges.rename(columns={'from': 'u', 'to': 'v', 'distance': 'length'}, inplace=True)
        gdf_nodes = geopandas.GeoDataFrame(df_nodes)
        nodes = df_nodes.set_index('id')
        gdf_edges = geopandas.GeoDataFrame(df_edges)
        gdf_edges['geometry'] = df_edges.apply(lambda row: crea_linestring(row, nodes), axis=1)
        return 0,gdf_nodes, gdf_edges
    except Exception as e:  
        print(f"Error during the get_network_osm: {e}.\n", flush = True)
        return 1, None, None
    return 1, None, None


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
        print(f"Error during the crea_linestring: {e}.\n", flush = True)        

# -----------------------------------------------------------------------------------------------------------------------------------


def calculate_edges_time_from_nodes(gdf_edges, by='foot'):  
    try:    
        if by == 'foot':
            coefficiente = COEFFICIENT_FOOT
        elif by == 'bike':
            coefficiente = COEFFICIENT_BIKE
        else:
            print(f"Error: Value '{by}' not valid. It should be 'foot' o 'bike'.\n")
            return 1, None 
               
        gdf_edges['slope'] = 0.0         
        gdf_edges = gdf_edges.dropna(subset=['geometry']) 
                    
        slope_abs = gdf_edges['slope'].abs()
        print(f"Value max of |slope|: {slope_abs.max()}\n")
        print(f"Value min of |slope|: {slope_abs.min()}\n")
        print(f"Value medium of |slope|: {slope_abs.mean()}\n")
        for index, row in gdf_edges.iterrows():
           
            velocita = coefficiente * math.exp(-3.5 * abs(gdf_edges.at[index, 'slope'] + 0.05))
            gdf_edges.at[index, 'velocita'] = velocita * (1000/60)

            gdf_edges.at[index, 'time'] = row['length'] / (gdf_edges.at[index, 'velocita'])
                        
        gdf_edges['velocita'] = gdf_edges['velocita'].astype('float32')        
        gdf_edges['time'] = gdf_edges['time'].astype('float32')     
       
        gdf_edges = gdf_edges.sort_values(by=['u', 'v', 'length']) #ordinamento in base alle colonne 'u', 'v' e 'length'.

        return 0, gdf_edges

    except Exception as e: 
        print(f"Error during the calculate_edges_time_from_nodes: {e}.\n", flush=True)
# -----------------------------------------------------------------------------------------------------------------------------------
# WALK SCORE FUNCTION


def walkScore_minuti(outputPath_bbox, category = 'all', by = 'foot',weight='time'):

    try:
        
        if not os.path.exists(outputPath_bbox):
            print(f"Error: The folder {outputPath_bbox} doesn't exist.\n")
            return 1, None
        
        if weight == 'time':
            peso = TEMPOMAX
        elif weight == 'space':
            if by == 'foot':
                DISTMAX_FOOT = (FOOT_SPEED / 3.6) * (TEMPOMAX * 60) #meters
                velocita = (FOOT_SPEED / 3.6)
                peso = DISTMAX_FOOT
            else:
                DISTMAX_BIKE = (BIKE_VEHICLE_SPEED / 3.6) * (TEMPOMAX * 60) #meters            
                velocita = (BIKE_VEHICLE_SPEED / 3.6)
                peso = DISTMAX_BIKE                            
        else:
            print(f"Error: Value '{weight}' non valido. Deve essere 'time' o 'space'.\n")
            return 1, None            
        nodes = pd.read_csv("{}/network/nodes.csv".format(outputPath_bbox), index_col=0)
        edges = pd.read_csv("{}/network/edges.csv".format(outputPath_bbox), index_col=[0,1])
        edges = edges.reset_index()
        
        if not edges.empty:
            if category=='all':
                list_string = ['restaurantcafe', 'education', 'marketgroc', 'postbank', 'park', 'entertainment', 'shop', 'health']
                restaurantcafe = pd.read_csv("{}/poi/restaurantcafe.csv".format(outputPath_bbox), index_col=0)
                education = pd.read_csv("{}/poi/education.csv".format(outputPath_bbox), index_col=0)
                marketgroc = pd.read_csv("{}/poi/marketgroc.csv".format(outputPath_bbox), index_col=0)
                postbank = pd.read_csv("{}/poi/postbank.csv".format(outputPath_bbox), index_col=0)
                park = pd.read_csv("{}/poi/park.csv".format(outputPath_bbox))#, index_col=0)
                entertainment = pd.read_csv("{}/poi/entertainment.csv".format(outputPath_bbox), index_col=0)
                shop = pd.read_csv("{}/poi/shop.csv".format(outputPath_bbox), index_col=0)
                health = pd.read_csv("{}/poi/health.csv".format(outputPath_bbox), index_col=0)
                pois = [restaurantcafe, education, marketgroc, postbank, park, entertainment, shop, health]
                #weights = [3,1,3,1,1,1,2,1]


             
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
            
            else:
                cat = pd.read_csv("{}/poi/{}.csv".format(outputPath_bbox,category), index_col=0)
                network = pandana.Network(nodes['x'], nodes['y'], edges['u'], edges['v'], edges[['time']])
                walk_score = nodes
                if not cat.empty:
                    network.set_pois(category = category, maxdist = peso, maxitems = 1, x_col = cat.lon,  y_col = cat.lat)
                    res = network.nearest_pois(distance = peso, category = category, num_pois = 1, include_poi_ids = False)                    
                    
                    if weight == 'time':
                        walk_score['media'] = res[1]
                    else:
                        walk_score['media'] = res[1] / velocita /60
             
            print('Function walkScore_minuti completed.\n', flush = True)
            
            return 0, walk_score    
        else:
            print('The edges file is empty\n.', flush = True)
            return 1, None

    except Exception as e: 
        print(f"Error during the walkScore_minuti: {e}.\n", flush = True)
        
#--------------------------------------------------------------------
#-----------------------------------------------------------------    
#COMPUTO

def computo(bbox_tassello, latCella, lonCella, raggio, outputPath_bbox, clip_layer_path, city_name, category = 'all',by = 'foot', weight='time'):
    
    try:
        
		# The folder di lavoro del tassello esiste? 
		# In caso negativo mi interrompo con Error e si blocca l'esecuzione del codice.
        if not os.path.exists(outputPath_bbox):
            print(f"Error: The folder {outputPath_bbox} doesn't exist.\n")
            return 1
            
        bbox = json.loads(bbox_tassello)
        lon = []
        lat= []
        rLon = longitudine_gradi(bbox, raggio)
        rLat =latitudine_gradi(bbox, raggio)
        nCelleX = round((bbox[3]-bbox[1])/lonCella)
        nCelleY = round((bbox[2]-bbox[0])/latCella)
    
        for i in range(int(nCelleY)+1):
            for j in range(int(nCelleX)+1):
                lat.append(bbox[0] + i * latCella)
                lon.append(bbox[1] + j * lonCella)
                lat.append(bbox[0] + i * latCella + np.sqrt(3)/2*rLat)
                lon.append(bbox[1] + j * lonCella + 3/2*rLon)
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
        #    print("❌ Errore in voronoi_regions_from_coords:", e)
        #    print("Numero centri:", len(centri))
        #    print("BBox:", bbox)
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
    
        grid = geopandas.sjoin(grid, centri, how='inner', op ='contains')
    
        grid = grid.to_crs(CRS_4326)
        print("Numero poligoni totali:", len(grid))
        print("Poligoni vuoti:", grid.geometry.is_empty.sum())
        print("Poligoni non validi:", (~grid.is_valid).sum())

        grid = grid.drop('index_right', axis = 1)
        
        # Chiamata della funzione walkScore_minuti        
        result, walk_score = walkScore_minuti(outputPath_bbox, category, by, weight)
        
        if walk_score is None or walk_score.empty:
            ws = []
            np.savetxt("{}/walkability_{}.csv".format(outputPath_bbox, category), ws, delimiter=';', fmt='%s', 
            header = 
            'geometry;marketgroc;restaurantcafe;education;health;postbank;park;entertainment;shop;overall_average;overall_max', 
            comments='')
            print('The walkScore_minuti function does not return a ws to work on.', flush = True)
            return 0
        else: 
            

            walk_score = geopandas.GeoDataFrame(walk_score, geometry = geopandas.points_from_xy(walk_score.x, walk_score.y))
           
            hexag = geopandas.sjoin(grid, walk_score, how='inner', op = 'contains')
            

            hexag = hexag.drop(columns=['highway'], errors='ignore')
            
            hexag = hexag.replace({'NaN' : np.nan})
            
            hexag = hexag.dissolve(by = hexag.index, aggfunc="mean")
            
            
            if category != 'all':
                categories = [category]  
            else: 
                categories = ['restaurantcafe', 'education', 'marketgroc', 'postbank', 'park', 'entertainment', 'shop', 'health']
            for cat in categories:
                if 'minutes_{}'.format(cat) not in hexag.columns:
                    hexag['minutes_{}'.format(cat)] = np.nan
            if category != 'all':
                for index, row in hexag.iterrows():
                    if pd.notnull(row.get('media', np.nan)):
                        hexag.at[index, f'minutes_{category}'] = row['media']
                        
            #hexag['countNaN'] = hexag.isnull().sum(axis=1)
            hexag['countNaN'] = hexag.drop(columns='geometry', errors='ignore').isnull().sum(axis=1)

            hexag = hexag[['geometry'] + ['minutes_{}'.format(cat) for cat in categories] + ['countNaN']]
            
            #Calcolo indice continuo (da 0 a 100)
            hexag['overall_average'] = None
            if category != 'all':
                list_string = [category]
                #weights_dict = {'restaurantcafe': 3, 'education': 1, 'marketgroc': 3, 'postbank': 1, 'park': 1, 'entertainment': 1, 'shop': 2, 'health': 1}
                #weights = [weights_dict.get(category, 1)]               
            else:    
                list_string = ['restaurantcafe', 'education', 'marketgroc', 'postbank', 'park', 'entertainment', 'shop', 'health']
                #weights = [3,1,3,1,1,1,2,1]
            for i in hexag.index:
                valori = []
                val100 = []
                #sommapesi = 0
                for j in range(0, len(list_string)):
                    val = hexag.at[i,'minutes_{}'.format(list_string[j])]
                    
                    if np.isnan(val):
                        valori.append(None)
                    else:
                        #valori.append(val*weights[j])
                        #sommapesi = sommapesi + weights[j]
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
            
            pd.set_option('display.max_columns', None)
            pd.set_option("display.max_rows", None)        
            minutes_cols = [col for col in hexag.columns if col.startswith('minutes_')]
            hexag[minutes_cols] = hexag[minutes_cols].round(2)
            hexag[minutes_cols] = hexag[minutes_cols].fillna('> 60')

            # Discrete index
            hexag['overall_max'] = '> 60'
            for i in hexag.index:
                if hexag.at[i,'countNaN'] == 0:
                    if category == 'all':
                        mins = [hexag.at[i,'minutes_restaurantcafe'], hexag.at[i,'minutes_education'], hexag.at[i,'minutes_marketgroc'], 
                                hexag.at[i,'minutes_postbank'], hexag.at[i,'minutes_park'], hexag.at[i,'minutes_entertainment'],
                                hexag.at[i,'minutes_shop'], hexag.at[i,'minutes_health']]
                    else:
                        mins = [hexag.at[i,f'minutes_{category}']]
                    
                    if all(val <= 15 for val in mins):
                        hexag.at[i,'overall_max'] = 15
                    elif any(val > 15 for val in mins) and all(val <=30 for val in mins): 
                        hexag.at[i,'overall_max'] = 30
                    else:
                        hexag.at[i,'overall_max'] = 60
                elif hexag.at[i,'countNaN'] < len(categories):
                    hexag.at[i,'overall_max'] = '> 60'
                    
            hexag = hexag.replace({None : np.nan})
            hexag = hexag.to_crs(CRS_3857) 
            if 'overall_average' in hexag.columns:
                hexag['overall_average'] = hexag['overall_average'].round(2)
            
            #geometry;marketgroc;restaurantcafe;education;health;postbank;park;entertainment;shop;countNaN;overall_average;city


            np.savetxt("{}/walkability_{}.csv".format(outputPath_bbox, category), hexag, delimiter=';', fmt='%s', 
            header = 
            'geometry;marketgroc;restaurantcafe;education;health;postbank;park;entertainment;shop;overall_average;overall_max', 
            comments='')
            clip_layer = geopandas.read_file(clip_layer_path)
            
            
            clip_layer = clip_layer.to_crs(EPSG_METRIC)
            hexag_clipped = geopandas.clip(hexag, clip_layer)

            print(f"Ritaglio completato: {len(hexag_clipped)} poligoni su {len(hexag)} totali")
            hexag_clipped.rename(
            columns=lambda c: c.replace('minutes_', '') if c.startswith('minutes_') else c,
            inplace=True
            )
            cols_to_keep = [
                'geometry',
                'marketgroc',
                'restaurantcafe',
                'education',
                'health',
                'postbank',
                'park',
                'entertainment',
                'shop',
                'overall_average',
                'overall_max'
            ]
            
            hexag_clipped = hexag_clipped[[c for c in cols_to_keep if c in hexag_clipped.columns]]

            hexag_clipped.to_file(
            f"{outputPath_bbox}/walkability_{category}_{city_name}.gpkg",
            layer=f"walkability_{category}_{city_name}",
            driver="GPKG"
            )
            return 0
    except Exception as e: 
        print(f"Error during the computo: {e}.\n", flush = True)
                           
                   

#save_output
def save_output(outputPath, category='all', by='foot'):
    try:
        if not os.path.exists(outputPath):
            print(f"Error: The folder {outputPath} doesn't exist.\n")
            return 1

        input_file = f"{outputPath}/walkability_{category}.csv"
        if not os.path.isfile(input_file):
            print(f"Error: Il file {input_file} doesn't exist.\n")
            return 1

        walkability = pd.read_csv(input_file, sep=';', header=0, index_col=False)

        np.savetxt(f"{outputPath}/walkability_{by}.csv", walkability, delimiter=';', fmt='%s',
                   header='geometry;marketgroc;restaurantcafe;education;health;postbank;park;entertainment;shop;overall_average;overall_max',
                   comments='')

        return 0
    except Exception as e:
        print(f"Error during the save_output function: {e}.\n", flush=True)

    