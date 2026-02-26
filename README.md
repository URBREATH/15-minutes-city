# 15-minutes-city
Open-source tool for 15-minute city analysis.

## Overview and Purpose

The **15-Minute City algorithm** is designed to assign a proximity index to urban services within a defined geographic area. It evaluates how easily residents can access Points of Interest (PoIs) on foot or by bicycle, following the “15-minute city” concept introduced by **Carlos Moreno**.  
This urban planning model envisions that most daily needs should be met within a 15-minute walk or bike ride from home.

---

## Key Features

- The tool uses **OpenStreetMap (OSM)** for the road network, while **POIs** can come from either **OSM** or **custom data** sources.
- The tool calculates travel time to **POIs** by walking or biking.
- **OSM POIs** are defined in the `osm_categories_tag.json` file, which contains the preconfigured POI categories. Each key in the JSON represents a category and maps to OSM tags and their possible values, which can be modified or extended. Below are the 9 preconfigured categories:

| poi_category_osm | description               |
|------------------|---------------------------|
| `marketgroc`     | Market and groceries      |
| `restaurantcafe` | Restaurants and cafés     |
| `education`      | Education                 |
| `health`         | Health                    |
| `postbank`       | Banks and post offices    |
| `park`           | Parks                     |
| `entertainment`  | Entertainment             |
| `shop`           | Shops                     |
| `transportstop`  | Transport stops           |

---

## Required Inputs
The script reads a `.ini` configuration file:

```.ini
[aoi]
bbox = [lat_min, lon_min, lat_max, lon_max] in EPSG:4326 defines the area of interest 
name = name of the area of interest 
[execution]
weight = time | distance
mode = walk | bike
walk_speed_kmh =  walking speed (default = 5.0 Km/h)  
bike_speed_kmh = biking speed (default = 15.0 Km/h) 
output_path = path to the folder
[poi]
poi_category_osm = all | one of the category in `osm_categories_tag.json`
poi_category_custom_name = comma-separated list; names are lowercased and spaces removed
poi_category_custom_csv = full CSV paths (comma-separated); required columns: id, lat, lon in EPSG:4326.
[park]
park_gates_source = osm | csv | road_intersect | virtual (default = osm)
park_gates_osm_buffer_m =  OSM park-gate buffer distance in meters (default 10.0)
park_gates_csv = full path to CSV file with park gates. Mandatory if park_gates_source = csv
park_gates_virtual_distance_m = distance in meters for virtual park gate generation (default 100).
[grid]
grid_gpkg = full path to a GPKG external grid file in EPSG:3857 
hex_diameter_m =  diameter (meters) of the hexagons of the hexagonal grid (default = 250.0)
clip_layer = full path to a GPKG polygon file in EPSG:3857 used to clip the area of interest (e.g., administrative borders, district boundaries..) 

```

**Minimum required parameters: aoi_bbox, aoi_name and execution_output_path**; default (poi_category_osm = ‘all’).

---
  
## Algorithm Workflow

### 1. Data Download

1. The street network is downloaded from OSM, limited to pedestrian or bicycle-accessible streets. If a network file already exists in the output_path folder, it is reused and not downloaded again.The same logic is applied to POIs.

2. Grid parameters are computed and stored in a CSV file (grid_parameters.csv), including the area extent and the hex_radius_m, defined as hex_diameter_m / 2.

3. Points of Interest (PoIs) are processed according to the selected source:

	- for OSM categories, data are downloaded only if the corresponding category CSV is not already present;

	- for custom categories, the provided CSV files are copied into the custom_poi folder if not already present;

---

### 2. Hexagonal Grid Generation

- The area of interest is divided into **hexagons** with a default hex_diameter_m of 250 m (hex_radius_m = 125 m), generated only where OSM street nodes exist.
---

### 3. Proximity Index Calculation

For each hexagon:

1. Travel times to the nearest PoI in each category are calculated; the model uses network-based accessibility calculations implemented through the **Pandana library** to find the nearest POI for each location. 
2. Only streets accessible by the chosen mode (foot or bike) are considered.
3. The default walking time used is **5 km/h**.
4. The default biking time used is **15 km/h**.
5. Travel times are computed for each POI category, together with two aggregate metrics: **overall_average** (mean travel time across categories) and **overall_max** (maximum travel time among categories).

---

### 4. Park Gate Management (POIs) and classification

All POIs categories are points; parks are polygons, but are represented using park gate points.

Each park is assigned access points, classified into three types depending on the **park_gates_source** parameter:

- **osm** - Gates from OSM located within 10 m of the park boundary (park_gates_osm_buffer_m). When downloaded from OSM, gates are identified using the tags in `park_osm_tag.json`

- **road_network** – Gates generated as intersections between the park perimeter and the street network, considering OSM street tagged in `park_road_network_tag.json`

- **virtual** – Virtual gates generated along the park perimeter every park_gates_virtual_distance_m meters.

---

## **Outputs:**
The output is a hexagon vector layer (clipped if a clipping polygon is provided) in EPSG:3857. Both formats include travel times for each service category, the average travel time, and the overall_max index:
- **CSV**
- **GPKG file**
---

##  Technical Architecture

### 1. Programming language and libraries

**Programming Language:** Python

**Qgis:** install qgis

**Libraries:**
Pandana, geopandas, numpy, pandas, osmnet, rtree, pyproj, shapely,
geovoronoi, fiona=1.9.5, rasterio, gdal, scipy, beautifulsoup, from qgis.core import *

### 2. QGIS Headless Implementation

The algorithm uses **QGIS in offscreen mode** to perform all geospatial computations.  
Initialization includes:
- Importing QGIS and Python libraries  
- Initializing the QGIS application and Processing framework

### 3. Execution

 Command line or IDE:

```ini
.../python3 main_15min.py ./config/parameters.ini > log.txt 2>&1 &
```

It is necessary to specify the correct path of the python instance. This command runs the Python script main_15min.py in the background, redirecting both standard output and error messages to the file log.txt.

---

## Possible Errors

In the logs, each error is prefixed with a timestamp, e.g.:

```
[timestamp] ERROR_CODE ERROR_MESSAGE
```
| Error Code | Error Message |
|------------|---------------|
| `ERR_001`  | parameters.ini not found or invalid: `<parameters.ini>` |
| `ERR_002`  | Missing required parameter: `oi_bbox \| aoi_name \| outputPath` |
| `ERR_003`  | outputPath invalid |
| `ERR_004`  | Invalid parameter value weight: `time \| distance` |
| `ERR_005`  | Invalid parameter value mode: `walk \| bike` |
| `ERR_006`  | Invalid parameter value poi_category_osm: `park \| restaurantcafe \| …` |
| `ERR_007`  | Invalid parameter value poi_category_custom_name: `Custom category cannot match OSM category` |
| `ERR_008`  | Invalid parameter value poi_category_custom: `Custom categories count must match CSV categories count` |
| `ERR_009`  | Invalid parameter value park_gates_source: `osm \| csv \| road_network \| virtual` |
| `ERR_010`  | park_gates_csv missing or invalid |
| `ERR_011`  | poi_category_custom_csv not found `<poi_category_custom_csv>` |
| `ERR_012`  | clip_layer_path not found `<clip_layer_path>` |
| `ERR_013`  | grid_path not found `<grid_path>` |

 
- Parameter poi_category_custom_name cannot be identical to any existing OSM category (poi_category_osm).
- poi_category_custom_name are normalized: spaces removed, converted to lowercase.
- Every custom category must have one corresponding CSV file, in the same order.
  
## Otput Folder Structure

Output directory is created at output_path. Inside it:

- **grid_parameters.csv**
  
- **walkability_all.csv**: if poi_category_osm = 'all' **or** more than one poi_category_custom_name is specified

- **walkability_<category>.csv**: if a specific poi_category_osm or poi_category_custom_name is selected (e.g., walkability_education.csv)

- **walkability_<category>_<aoi_name>.gpkg** or **walkability_all_<aoi_name>.gpkg**

-  **osm_pois/**: contains one CSV for each osm category

- **custom_pois/**: contains CSV files for custom categories.

- **network/**: contains: nodes.csv and edges.csv

```

├── config/
│   ├── parameters.ini                   
│   ├── osm_categories_tag.json
│   ├── park_road_network_tag.json
│   ├── park_osm_tag.json   
├── scripts/
│   ├── errors.py                        
│   ├── index_processing.py             
│   ├── parameters.py      
│   ├── park_gates.py
├── boundary.gpkg                        
├── main_15min.py                       


```
After executing the script, the following structure will be created:  
```

├── config/
│   ├── parameters.ini                   
│   ├── osm_categories_tag.json
│   ├── park_road_network_tag.json
│   ├── park_osm_tag.json         
├── scripts/
│   ├── errors.py                        
│   ├── index_processing.py 
│   ├── parameters.py      
│   ├── park_gates.py
├── boundary.gpkg                        
├── main_15min.py                        


Output directory (output_path = parent_path/{...}):

output_path/
├── walkability_<category>_<aoi_name>.csv 	   
├── walkability_<category>_<aoi_name>.gpkg
├── grid_parameters.csv
├── osm_pois/                                  
│   ├── marketgroc.csv
│   ├── restaurantcafe.csv
│   ├── education.csv
│   ├── health.csv
│   ├── postbank.csv
│   ├── park.csv
│   ├── entertainment.csv
│   ├── shop.csv
├── costum_pois/                               
└── network/                                   
    ├── edges.csv
    └── nodes.csv

```
---




## Main Scripts

1.	**main_15min.py**

This is the main workflow script for the 15-Minute City Proximity Index. Its main responsibilities are:

o	Parameter handling: Reads configuration from a .ini.

o	Perform each step by calling the functions contained in index_processing.py.

o	Logging and timing: Prints progress and timing for each step.

2.	**index_processing.py**

Contains helper functions used by main_15min.py:

o	Bounding box preparation

o	Data download: Downloads street networks and Points of Interest (PoIs), filtered by mode of transport (walking or biking) and category. 

o	Proximity computation: Calls computo to calculate travel times to PoIs for each hexagonal tile and computes the proximity index.

o	Output saving: Uses save_output to merge results and save CSV and GIS files for further analysis.

3.	**park_gates.py**

Manages gates for “park” category.

4.	**parameters.py**

Provides functions for reading input parameters from .ini file.

5.	**errors.py**

Error handler module that defines error codes.
