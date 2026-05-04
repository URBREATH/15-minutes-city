# 15-minutes-city 

**Provided by:** Deda next

---
## Description
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

-  The road network is retrieved using the **Pandana library**, with data sourced via the Overpass API.
-  The tool uses the **Pandana library** to find the nearest POI for each location.
-  The tool divides the area of interest into hexagons (default diameter: 250 m), created only where OSM road nodes are present.
-  The tool outputs a GPKG file in EPSG:3857 by default.
---

## Execution

**Programming Language:** Python

**Libraries:** Pandana

(Optional) Set variables only if publishing to MinIO:

```
MINIO_ACCESS_KEY   – Access key used to authenticate with the MinIO service
MINIO_SECRET_KEY   – Secret key associated with the access key
MINIO_ENDPOINT_URL – URL of the MinIO endpoint
```

### Local 

Run:
```
main_15min.py parameters.ini
```
---

### API

The tool is exposed via a REST API accepting JSON payloads.

- Endpoint: https://15-min-dev.urbreath.tech/execute

- Method: POST
 
- Content-Type: application/json

API run:
```
curl -X POST [endpoint] -H "Content-Type: application/json" -d @parameters.json
```

The output is a hexagon vector layer (clipped if a clipping polygon is provided) available in CSV and GPKG formats. Both formats include walking times for each service category, the average walking time (mean walking time across categories), and the overall_max index (maximum walking time among categories).

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
output_format = csv | gpkg | geojson
output_EPSG = output CRS EPSG code (metric; default: 3857)
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

**Minimum required parameters: area of interest and the path folder/filename**; default (poi_category_osm = ‘all’). 

A separate `parameters_<city>.ini` file is created for each city that requires computation, stored in the parameters folder.

The script generates a hexagonal grid and saves it as grid.gpkg in the working directory, with the option to use an external grid via the grid_gpkg parameter.

Grid parameters, such as area extent and hexagon radius, are stored in grid_parameters.csv.

If virtual_nodes = true, a node is added at each hexagon centroid and connected to the nearest OSM street node, ensuring full network coverage.


## JSON payload

The API version required a ```parameters.json``` file:

```
{
  "aoi": {
    "bbox":[lat_min, lon_min, lat_max, lon_max] in EPSG:4326 defines the area of interest 
  },
  "execution": {
    "output_local_path": path folder,
    "output_minio_path": null,
    "filename":  <area of interest>_15min_<osm or local_data>,
    "weight": "time",
    "mode": "walk",
    "walk_speed_kmh": 5.0,
    "bike_speed_kmh": 15.0,
    "output_format":,
    "output_EPSG":
  },
  "poi": {
    "poi_category_osm": "all",
    "poi_category_custom_name": null,
    "poi_category_custom_csv": null,
    "poi_category_custom_style": null
  },
  "park": {
    "park_gates_source": "osm",
    "park_gates_osm_buffer_m": 10.0,
    "park_gates_csv": null,
    "park_gates_virtual_distance_m": 100.0
  },
  "grid": {
    "grid_gpkg": null,
    "hex_diameter_m": 250,
    "clip_layer": null,
    "virtual_nodes": False
  }
}
```
---

### 4. Park Gate Management (POIs) and classification

All POIs categories are points; parks are polygons, but are represented using park gate points.

Each park is assigned access points, classified into three types depending on the **park_gates_source** parameter:

- **osm** - Gates from OSM located within 10 m of the park boundary (park_gates_osm_buffer_m). When downloaded from OSM, gates are identified using the tags in `park_gate_osm_tag.json`

- **road_network** – Gates generated as intersections between the park perimeter and the street network, considering OSM street tagged in `park_road_network_osm_tag.json`

- **virtual** – Virtual gates generated along the park perimeter every park_gates_virtual_distance_m meters.

---

##  Errors

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
| `ERR_018`  | Invalid parameter value `output_format` |
| `ERR_019`  | Invalid parameter value `output_EPSG` | 

---

## Publication on Urbreath Geoserver 

The tool supports automatic publication to GeoServer and IDRA if output_minio_path is specified.

A publish.json file is always generated by default, containing all the required information to publish the output layers and their associated styles.

For OSM categories, the .sld files located in the `style` folder are used, while for POI categories, custom .sld files can be provided using the poi_category_custom_style parameter.

---
## Output Folder Structure

Output directory is created at output_local_path. Inside it:

- **grid**: contains the **grid_parameter.csv** and the **grid.gpkg**
  
- **output**
  
- **_publish.json** (JSON for automatic publication on Geosever)

-  **osm_pois**: contains one CSV for each osm category

- **custom_pois**: contains CSV files for custom categories.

- **osm_network**: contains: nodes.csv and edges.csv

```
output_local_path/
├── output/
│   ├── <filename>.gpkg
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

## Contact

- chiara.savoldi@dedagroup.it  
- martina.forconi@dedagroup.it  

