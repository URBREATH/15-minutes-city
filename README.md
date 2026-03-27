# 15-minutes-city 

The **15-Minute City tool** is designed to assign a proximity index to urban services within a defined geographic area. It evaluates how easily residents can access Points of Interest (PoIs) on foot or by bicycle, following the “15-minute city” concept introduced by **Carlos Moreno**.  
This urban planning model envisions that most daily needs should be met within a 15-minute walk or bike ride from home.

---

## Key Features

- The tool uses **OpenStreetMap (OSM)** for the road network, while **POIs** can come from either **OSM** or **custom data** sources.
- The tool calculates walking or biking time to **POIs**.
- **OSM POIs** are defined in the `poi_category_osm_tag.json` file, which contains the preconfigured POI categories. Each key in the JSON represents a category and maps to OSM tags and their possible values, which can be modified or extended. New categories can be added. Below are the 9 preconfigured categories:

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
| `transport`      | Public transport stops    |

---

## Parameters CLI
The CLI version of the script reads a `.ini` configuration file:

```.ini
[aoi]
bbox = [lat_min, lon_min, lat_max, lon_max] in EPSG:4326 defines the area of interest 
[execution]
output_local_path = path folder
output_minio_path = path folder on MINIO
filename = <area of interest>_15min_<osm or local_data> 
weight = time | distance
mode = walk | bike
walk_speed_kmh =  walking speed (default = 5.0 Km/h)  
bike_speed_kmh = biking speed (default = 15.0 Km/h) 
[poi]
poi_category_osm = all | one of the category in `poi_category_osm_tag.json`
poi_category_custom_name = comma-separated list, names are lowercased and spaces removed
poi_category_custom_csv = full CSV paths (comma-separated) with required columns: id, lat, lon in EPSG:4326.
poi_category_custom_style = path to the custom sld for geoserver publication (comma-separated)
[park]
park_gates_source = osm | csv | road_intersect | virtual (default = osm)
park_gates_osm_buffer_m =  OSM park-gate buffer distance in meters (default 10.0)
park_gates_csv = full path to CSV file with park gates. Mandatory if park_gates_source = csv
park_gates_virtual_distance_m = distance in meters for virtual park gate generation (default 100).
[grid]
grid_gpkg = full path to a GPKG external grid file in EPSG:3857 
hex_diameter_m =  diameter (meters) of the hexagons of the hexagonal grid (default = 250.0)
clip_layer = full path to a GPKG polygon file in EPSG:3857 used to clip the area of interest 
virtual_nodes = true/false
```

**Minimum required parameters: area of interest and the path folder/filename**; default (poi_category_osm = ‘all’). The filename identifies the area of interest and is used as the output name for both the CSV and GPKG files.

A separate `parameters_<city>.ini` file is created for each city that requires computation, stored in the parameters folder.

The script automatically saves the hexagonal grid to the working grid folder, naming it grid.gpkg. The script also allows the use of an external grid, if provided via the `grid_gpkg` parameter.
 
---
  
## Algorithm Workflow

### 1. OSM Data Download

- The street network is downloaded from OSM through the **Pandana library**, limited to pedestrian or bicycle-accessible streets. If a network file already exists in the output_local_path folder, it is reused and not downloaded again.The same logic is applied to POIs.

- Points of Interest (POIs) are handled as follows: OSM category data is downloaded only if the corresponding CSV is missing, while custom category CSVs are copied into the custom_poi folder if not already present.

---

### 2. Hexagonal Grid Generation

The area of interest is divided into **hexagons** with a default hex_diameter_m (125 m), generated only where OSM street nodes exist. Grid parameters are computed and stored in a CSV file (grid_parameters.csv), including the area extent and the hex_radius_m, defined as hex_diameter_m / 2. If virtual_nodes = true, a virtual node is placed at each hexagon centroid, and a connecting edge is added to the nearest OSM street node, extending the network to ensure full hexagon coverage.

---

### 3. Proximity Index Calculation

For each hexagon:

- Walking times to the nearest PoI in each category are calculated; the model uses the **Pandana library** to find the nearest POI for each location. 
- Walking times are computed for each POI category, together with two aggregate metrics: **overall_average** (mean walking time across categories) and **overall_max** (maximum walking time among categories).

---

### 4. Park Gate Management (POIs) and classification

All POIs categories are points; parks are polygons, but are represented using park gate points.

Each park is assigned access points, classified into three types depending on the **park_gates_source** parameter:

- **osm** - Gates from OSM located within 10 m of the park boundary (park_gates_osm_buffer_m). When downloaded from OSM, gates are identified using the tags in `park_gate_osm_tag.json`

- **road_network** – Gates generated as intersections between the park perimeter and the street network, considering OSM street tagged in `park_road_network_osm_tag.json`

- **virtual** – Virtual gates generated along the park perimeter every park_gates_virtual_distance_m meters.

---

## **Outputs:**

The output is a hexagon vector layer (clipped if a clipping polygon is provided) available in CSV and GPKG formats. Both formats include walking times for each service category, the average walking time, and the overall_max index.

---

##  Technical Architecture

### 1. Programming language and libraries

**Programming Language:** Python

**Qgis:** The algorithm uses **QGIS in offscreen mode** to perform all geospatial computations.  Initialization includes:

- Importing QGIS and Python libraries  
- Initializing the QGIS application and Processing framework

**Libraries:** Pandana

### 2. Execution

Set the following environment variables only when running the script with direct MinIO publishing. Not required for local execution.

```
MINIO_ACCESS_KEY   – Access key used to authenticate with the MinIO service
MINIO_SECRET_KEY   – Secret key associated with the access key
MINIO_ENDPOINT_URL – URL of the MinIO endpoint
```

 Command for launch:

```
main_15min.py parameters.ini
```
---

## Possible Errors

In the logs, each error is prefixed with a timestamp, e.g.:

```
[timestamp] ERROR_CODE ERROR_MESSAGE
```
| Error Code | Error Message |
|------------|---------------|
| `ERR_001`  | parameters.ini not found or invalid: `<parameters.ini>` |
| `ERR_002`  | Missing required parameter: `oi_bbox \| filename \| outputPath` |
| `ERR_003`  | output_local_path invalid |
| `ERR_004`  | `Missing required MinIO configuration:  MINIO_ACCESS_KEY  \|  MINIO_SECRET_KEY  \| MINIO_ENDPOINT_URL` |
| `ERR_005`  | Invalid parameter value weight: `time \| distance` |
| `ERR_006`  | Invalid parameter value mode: `walk \| bike` |
| `ERR_007`  | Invalid parameter value poi_category_osm: `park \| restaurantcafe \| …` |
| `ERR_008`  | Invalid parameter value poi_category_custom_name: `Custom category cannot match OSM category` |
| `ERR_009`  | Invalid parameter value poi_category_custom: `Custom categories count must match CSV categories count` |
| `ERR_010`  | Style requires at least one csv |
| `ERR_011`  | More styles than csv categories |
| `ERR_012`  | poi_category_custom_style not found |
| `ERR_013`  | Invalid parameter value park_gates_source: `osm \| csv \| road_network \| virtual` |
| `ERR_014`  | park_gates_csv missing or invalid |
| `ERR_015`  | poi_category_custom_csv not found `<poi_category_custom_csv>` |
| `ERR_016`  | clip_layer not found `<clip_layer>` |
| `ERR_017`  | grid_gpkg not found `<grid_gpkg>` |
 
  
## Publication on Geoserver 

The tool supports automatic publication to GeoServer and IDRA if output_minio_path is specified.

A publish.json file is always generated by default, containing all the required information to publish the output layers and their associated styles.

For OSM categories, the .sld files located in the `style` folder are used, while for POI categories, custom .sld files can be provided using the poi_category_custom_style parameter.


## Log rotation

All messages are written to `15min_logger.log` in the `log` folder, with size-based log rotation enabled via a RotatingFileHandler. When the file reaches the configured maximum size (10 MB), a rollover occurs and a new log file is created.

A maximum of three rotated log files are retained (backupCount=3), with older files automatically discarded.


## Output Folder Structure

Output directory is created at output_local_path. Inside it:

- **grid**: contains the **grid_parameter.csv** and the **grid.gpkg**
  
- **`<filename>.csv`**
  
- **`<filename>.gpkg`**

- **_publish.json** (JSON for automatic publication on Geosever)

-  **osm_pois**: contains one CSV for each osm category

- **custom_pois**: contains CSV files for custom categories.

- **osm_network**: contains: nodes.csv and edges.csv

```
output_local_path/
├── <filename>.csv   
├── <filename>.gpkg
├── _publish.json 
├── grid/
│   ├── grid_parameter.csv
│   ├── grid.gpkg
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
└── osm_network/                                   
    ├── edges.csv
    └── nodes.csv

```
---


## Scripts

1.	**main_15min.py:** handles parameters from a .ini, executes steps via index_processing.py functions, and logs progress and timing.

2.	**index_processing.py:** contains functions for bounding box preparation, data download (street networks and POIs by transport mode and category), proximity computation, and output saving.

3.	**park_gates.py:** manages gates for “park” category.

4.	**parameters.py:** provides functions for reading input parameters from .ini file.

5.	**errors.py:** error handler module that defines error codes.

6.	**logger.py:** log rotation.
