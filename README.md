# 15-minutes-city
Open-source tool for 15-minute city analysis.

## Overview and Purpose

The **15-Minute City algorithm** is designed to assign a proximity index to urban services within a defined geographic area. It evaluates how easily residents can access Points of Interest (PoIs) on foot or by bicycle, following the “15-minute city” concept introduced by **Carlos Moreno**.  
This urban planning model envisions that most daily needs should be met within a 15-minute walk or bike ride from home.

---

## Key Features

- The tool uses either **OpenStreetMap (OSM)** or **costum data** as its data source.
- Calculates travel time to **POIs** by walking or biking.
- The tool measures accessibility to **9 fixed categories of OSM POIs**, configurable via the `config/osm_categories_tag.json` file. Each category corresponds to one or more OSM tags and values, which can be modified or extended.

| poi_category_osm name     | poi_category_osm |
|---------------------------|------------------|
| Market and groceries      | `marketgroc`     |
| Restaurants and cafés     | `restaurantcafe` |
| Education                 | `education`      |
| Health                    | `health`         |
| Banks and post offices    | `postbank`       |
| Parks                     | `park`           |
| Entertainment             | `entertainment`  |
| Shops                     | `shop`           |
| Transport stops           | `transportstop`  |

Each key in `osm_categories_tag.json` represents a category and maps to OSM tags and possible values.  
- The tool measures accessibility to **custom POIs** if specified. 

---

## Required Inputs
The script reads a `.ini` configuration file to dynamically configure inputs for the area of interest.
A separate parameter.ini file is created for each city, containing all city-specific parameters. At runtime, the appropriate configuration file must be provided depending on the city being processed. For example, to run the analysis for Parma, the parameter_parma.ini file is used.

**Example (`parameters.ini`):**

```ini
[aoi]
bbox = 
name = 
clip_layer_path =
weight = time
mode = walk
walk_speed_kmh =   
bike_speed_kmh = 
[poi]
poi_category_osm = 
poi_category_custom_name = 
poi_category_custom_csv = 
[park]
park_gates_source = 
park_gates_osm_buffer_m =  
park_gates_csv_path = 
park_gates_virtual_distance_m =  
[grid]
grid_path = 
hex_diameter_m = 
[execution]
outputPath = 
```

```[aoi]```

**bbox**: rectangular bounding box → defines the area of interest where the index is computed (specified as [lat_min, lon_min, lat_max, lon_max] in EPSG:4326)

**name**: name of the area of interest for which the index is calculates

**clip_layer_path**: path of the boundary polygon → polygon used to limit or clip the area of interest (e.g., administrative borders, district boundaries..) 

**weight**: measurement criterion  → criterion used for accessibility computation (time or distance)

**mode**: mode of transportation considered (pedestrian or cycling, default = 'walk’ or 'bike')

**walk_speed_kmh**: walking speed (default = 5 Km/h)  

**bike_speed_kmh**: biking speed (default = 15 Km/h) 

```[poi]```

**poi_category_osm**: service category for which the index is calculated (one of 9 categories ['marketgroc','restaurantcafe','education','health','postbank','park','entertainment','shop', 'transportstop'] or 'all' for a combined score)

**poi_category_custom_name**: list of custom categories for which the index is calculated. They must be provided as a comma-separated string. The script automatically normalizes the names by removing internal spaces and converting them to lowercase.

**poi_category_custom_csv**: CSV files from which the script reads data for custom categories. The full paths of the CSV files must be provided, separated by commas. The file must include a minimum structure consisting of 'id', 'lat', and 'lon' columns, with geographic coordinates expressed in EPSG:4326.

```[park]```

**park_gates_source**: source for park gates: osm | csv | road_intersect | virtual. Default: osm.

**park_gates_osm_buffer_m**: buffer distance (meters) applied when park_gates_source = osm to filter gates near parks. Default: 10.

**park_gates_csv_path**: path to CSV file with park gates. Mandatory if park_gates_source = csv. 

**park_gates_virtual_distance_m**: distance in meters used when park_gates_source = virtual to generate virtual gates along parks. Default: 100.

```[grid]```

**grid_path**: grid path → path to an external grid to be used

**hex_diameter_m** : diameter of the hexagons of the hexagonal grid

```[execution]```

**outputPath**: output folder → folder where output files and results will be stored


**Minimum required parameters: aoi_bbox, aoi_name and execution_outputPath.** If poi_category_osm or poi_category_custom_name are not specified, the script considers poi_category_osm = ‘all’ and proceeds to download the 9 categories from OSM.

---

  
## Algorithm Workflow

### 1. Data Download

1. A dedicated folder is created for the area of interest at the indicated outputPath.  
2. If the folder already exists, the process does not overwrite it, preserving previous work.  
3. Key spatial parameters (area size in lat/lon and representative radius) are computed and stored in a CSV file (unique_bbox.csv).  
4. The street network is downloaded from OSM, restricted to pedestrian- or bicycle-accessible streets, depending on the selected mode of travel.  
5. PoIs corresponding to the selected categories are retrieved.

---

### 2. Hexagonal Grid Generation

- The study area is divided into **hexagonal tiles** with a diameter of 250 m (side = 125 m), generated only where OSM street nodes exist.  
---

### 3. Proximity Index Calculation

For each hexagon:

1. Travel times to the nearest PoI in each service category are calculated; the model uses network-based accessibility calculations implemented through the **Pandana library** to find the nearest POI for each location. 
2. Only streets accessible by the chosen mode (foot or bike) are considered.
3. The walking time used is configurable. The default is **5 km/h**.
4. The biking time used is configurable. The default is **15 km/h**.
5. An average travel time (`overall_average`)  across all categories is computed (sum of POI minutes divided by the number of categories).  
6. Each hexagon is assigned a value (`overall_max`) based on the maximum travel time

---

### 4. Park Gate Management (POIs) and classification

All service categories in OSM are represented as point features, except for parks, which use park gates as points.

Each park is assigned access points, classified into three types depending on the park_gates_source parameter:

- **Type A**: Gates from OSM located within 10 m of the park boundary (park_gates_osm_buffer_m). When downloaded from OSM, gates are identified using the following tags:

```barrier = gate or barrier = entrance or entrance = yes```

- **Type B** – Gates generated as intersections between the park perimeter and the street network, considering any OSM street tagged as:

```highway	=
primary, secondary, tertiary
primary_link, secondary_link, tertiary_link
unclassified
residential, living_street, service, pedestrian, track
footway, bridleway, corridor, path
steps, ladder, elevator
road
cycleway


footway = sidewalk, crossing, traffic_island


cycleway =
lane
track
share_busway
shared_lane
crossing, link
```

- **Type C** – Virtual gates generated along the park perimeter every park_gates_virtual_distance_m meters.


The algorithm manages gates as follows:

- Supports external gates via CSV or automatically downloaded OSM gates.

- Gate generation depends on park_gates_source:
  - osm → Type A gates within park_gates_osm_buffer_m from the park boundary.

  - csv → Gates read from the CSV specified in park_gates_csv_path, which must include at least id, lat, and lon in EPSG:4326.

  - road_intersect → Type B gates.

  - virtual → Type C gates generated every park_gates_virtual_distance_m meters along the park perimeter.


---

## **Outputs:**
The output consists of a vector hexagon layer, provided in two formats (EPSG:3857):
- **CSV**, clipped if a clipping polygon is provided
- **GPKG file**, clipped if a clipping polygon is provided

Both formats contain travel times for each service category, the average travel time, and the overall_max index.

---


## Possible Errors

The tool uses error codes to report issues during execution. Each error has a code and a message. In the logs, each error is prefixed with a timestamp, e.g.:

```
[timestamp] ERROR_CODE  ERROR_MESSAGE
```

| Error Code | Error Message |
|------------|---------------|
| `ERR_001` | parameters.ini not found or invalid: `<parameters.ini>` |
| `ERR_002` | Missing required parameter: `oi_bbox | aoi_name | outputPath` |
| `ERR_003` | outputPath invalid |
| `ERR_004` | Invalid parameter value weight: `time | distance` |
| `ERR_005` | Invalid parameter value mode: `walk | bike` |
| `ERR_006` | Invalid parameter value poi_category_osm: `park | restaurantcafe | …` |
| `ERR_007` | Invalid parameter value poi_category_custom_name: `Custom category cannot match OSM category` |
| `ERR_008` | Invalid parameter value poi_category_custom: `Custom categories count must match CSV categories count` |
| `ERR_009` | Invalid parameter value park_gates_source: `osm | csv | road_network | virtual` |
| `ERR_010` | park_gates_csv_path missing or invalid |
| `ERR_011` | poi_category_custom_csv not found `<poi_category_custom_csv>` |
| `ERR_012` | clip_layer_path not found `<clip_layer_path>` |
| `ERR_013` | grid_path not found `<grid_path>` |

- The script must always be launched with a valid `.ini` configuration file (`ERR_001`).  
- **Minimum required parameters** in the section are: `aoi_bbox`, `aoi_name`, and `execution_outputPath`. Missing any triggers `ERR_002`.  
- All paths (output folder, CSVs, clip layer, grid) must exist when required.  
- Parameters like `weight`, `mode`, `poi_category_osm`, and `park_gates_source` are validated against allowed values. 
- Parameter poi_category_custom_name cannot be identical to any existing OSM category (poi_category_osm).
- poi_category_custom_name are normalized: spaces removed, converted to lowercase.
- Multiple custom categories (poi_category_custom_name) must be listed comma-separated.
- CSV files for the custom categories must also be listed comma-separated, in the same order as the categories. The first category uses the first CSV, etc.
- Every custom category must have one corresponding CSV file, in the same order.
  
## Otput Folder Structure

Output directory is created at outputPath. Inside it:

- **unique_bbox.csv** → stores key spatial parameters (bounding box extent and representative radius)

- **walkability_all_.csv** → if poi_category_osm = 'all' **or** more than one poi_category_custom_name is specified

- **walkability_<category>.csv** → if a specific poi_category_osm or poi_category_custom_name is selected (e.g., walkability_education.csv)

- **walkability_<category>_<aoi_name>.gpkg** or **walkability_all_<aoi_name>.gpkg** → spatial results, clipped to the optional boundary

- Points of Interest (PoIs)

  - Folder: **osm_pois/** → contains one CSV for each osm category: ['marketgroc', 'restaurantcafe', 'education', 'health', 'postbank', 'park', 'entertainment', 'shop', 'transportstop']

	- If poi_category_osm = 'all' → all csv are downloaded.
	
	- If a specific OSM category is selected → only the specified csv is downloaded.

  - Folder: **custom_pois/** – contains CSV files for custom categories.

	- If poi_category_custom_name is specified → each CSV file (poi_category_custom_csv) is copied into the folder.

- Street Network

  - Folder: **network/** → contains: nodes.csv and edges.csv

```

├── config/
│   ├── parameters.ini                   # Run configuration file
│   ├── osm_categories_tag.json          # osm tags used
├── scripts/
│   ├── errors.py                        # Errors handler
│   ├── index_processing.py             
│   ├── parameters.py      
│   ├── park_gates.py
├── boundary.gpkg                        # Optional GeoPackage for clipping
├── main_15min.py                        # Main Python script


```
After executing the script, the following structure will be created:  
```

├── config/
│   ├── parameters.ini                   # Run configuration file
│   ├── osm_categories_tag.json          # osm tags used
├── scripts/
│   ├── errors.py                        # Errors handler
│   ├── index_processing.py 
│   ├── parameters.py      
│   ├── park_gates.py
├── boundary.gpkg                        # Optional GeoPackage for clipping
├── main_15min.py                        # Main Python script


Output directory (output_path = parent_path/{...}):

output_path/
├── walkability_<category><aoi_name>.csv 	   # Walkability results per category, clipped to boundary if provided
├── walkability_<category>_<aoi_name>.gpkg     # Spatial walkability results, clipped to boundary if provided
├── osm_pois/                                  # OSM Points of Interest by category
│   ├── marketgroc.csv
│   ├── restaurantcafe.csv
│   ├── education.csv
│   ├── health.csv
│   ├── postbank.csv
│   ├── park.csv
│   ├── entertainment.csv
│   ├── shop.csv
├── costum_pois/                               # custom Points of Interest by category
└── network/                                   # Street network
    ├── edges.csv
    └── nodes.csv

```
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

**Input Data:** OSM network and PoIs

**Output Data:** CSV and GPKG files with travel times, overall_average, overall_max

Execution: Command line or IDE:

```ini
.../python3 main_15min.py ./config/parameters.ini > log.txt 2>&1 &
```

It is necessary to specify the correct path of the python instance. This command runs the Python script main_15min.py in the background, redirecting both standard output and error messages to the file log.txt.

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
