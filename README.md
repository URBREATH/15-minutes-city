# 15-minutes-city 

**Provided by:** Deda next

---
## Description
The **15-Minute City tool** is designed to assign a proximity index to urban services within a defined geographic area. It evaluates how easily residents can access Points of Interest (PoIs) on foot or by bicycle, following the “15-minute city” concept introduced by **Carlos Moreno**.  
This urban planning model envisions that most daily needs should be met within a 15-minute walk or bike ride from home.

This is the open-source version of the tool, but there is also a proprietary version that includes orographic integration and tiling.

---

## Key Features

- The tool uses **OpenStreetMap (OSM)** for the road network, while **POIs** can come from either **OSM** or **custom data** sources.
- It calculates walking or biking time to **POIs**.
- The road network is retrieved using the **Pandana library**, with data sourced via the Overpass API.
- The tool uses the **Pandana library** to find the nearest POI for each location.
- It divides the area of interest into hexagons (default diameter: 250 m), created only where OSM road nodes are present. The script saves the hexagonal grid as grid.gpkg in the working directory, with the option to use an external grid via the grid_gpkg parameter. Grid parameters, such as area extent and hexagon radius, are stored in grid_parameters.csv.
- The output is a hexagon vector layer (clipped if a clipping polygon is provided) available in CSV and GPKG formats and EPSG:3857 by default. Both formats include walking times for each service category, the average walking time (mean walking time across categories), and the overall_max index (maximum walking time among categories).
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

## Execution

(Optional) Set variables only if publishing to MinIO:

```
MINIO_ACCESS_KEY   – Access key used to authenticate with the MinIO service
MINIO_SECRET_KEY   – Secret key associated with the access key
MINIO_ENDPOINT_URL – URL of the MinIO endpoint
```

### CLI execution

```
main_15min.py parameters.ini
```

---  
## Parameters CLI
The CLI version of the script reads a `.ini` configuration file:

```.ini
[aoi]
bbox = [lat_min, lon_min, lat_max, lon_max] in EPSG:4326 defines the area of interest 
[execution]
output_local_path = path folder
output_minio_path = path folder on MINIO
filename = name of the output file 
weight = time | distance
mode = walk | bike
walk_speed_kmh =  walking speed (default = 5.0 Km/h)  
bike_speed_kmh = biking speed (default = 15.0 Km/h)
output_format = csv | gpkg | geojson
output_EPSG = output CRS EPSG code (metric; default: 3857)
[network]
network_edges = full path to a csv file with u,v,length,time columns
network_nodes =	full path to a csv file with y,x,type columns in EPSG:4326
[poi]
poi_category_osm = all | one of the category in `poi_category_osm_tag.json`
poi_osm_path = path to the folder containing previously downloaded POI CSV files to be reused
poi_category_custom_name = comma-separated list, names are lowercased and spaces removed
poi_category_custom_csv = full CSV paths (comma-separated) with required columns: id, lat, lon in EPSG:4326.
poi_category_custom_style = path to the custom sld for geoserver publication (comma-separated)
poi_category_extended_name = comma-separated list, names are lowercased and spaces removed
poi_category_extended_csv = full CSV paths (comma-separated) with required columns: id, lat, lon in EPSG:4326.
poi_category_extended_style = path to the custom sld for geoserver publication (comma-separated)
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

If virtual_nodes = true, a node is added at each hexagon centroid and connected to the nearest OSM street node, ensuring full network coverage.

If poi_category_extended_name and its associated fields (poi_category_extended_csv, poi_category_extended_style) are set, an additional output named filename_extended will be produced, containing the results computed only on the specified extended categories, without the overall results.
extended categories are excluded from the combined computation with the other categories (OSM + custom) and from the overall indexes computation.

### API execution

The tool is exposed via a REST API accepting JSON payloads.

- Endpoint: https://15-min-dev.urbreath.tech/execute

```
curl -X POST [endpoint] -H "Content-Type: application/json" -d @parameters.json
```

## JSON payload

The API version required a ```parameters.json``` file:

```
{
  "aoi": {
    "bbox": null
  },
  "execution": {
    "output_local_path": null,
    "output_minio_path": null,
    "filename": null,
    "weight": "time",
    "mode": "walk",
    "walk_speed_kmh": 5.0,
    "bike_speed_kmh": 15.0,
    "output_format": null,
    "output_EPSG": null
  },
  "network": {
    "network_edges": "",
    "network_nodes": ""
  },
  "poi": {
    "poi_category_osm": "all",
    "poi_category_custom_name": null,
    "poi_category_custom_csv": null,
    "poi_category_custom_style": null,
    "poi_category_extended_name": null,
    "poi_category_extended_csv": null,
    "poi_category_extended_style ": null

  },
  "park": {
    "park_gates_source": "osm",
    "poi_osm_path": "",
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

- **osm** - Gates from OSM located within the meter, indicated with the parameter park_gates_osm_buffer_m, of the park boundary. When downloaded from OSM, gates are identified using the tags in `park_gate_osm_tag.json`

- **road_network** – Gates generated as intersections between the park perimeter and the street network, considering OSM street tagged in `park_road_network_osm_tag.json`

- **virtual** – Virtual gates generated along the park perimeter every park_gates_virtual_distance_m meters.

---

##  Errors

| Error Code | Error Message |
|------------|---------------|
| `ERR_001`  | parameters.ini not found or invalid: `<parameters.ini>` |
| `ERR_002`  | Missing required parameter: `oi_bbox \| filename \| outputPath` |
| `ERR_003`  | output_local_path invalid |
| `ERR_004`  | Missing required MinIO configuration: `MINIO_ACCESS_KEY \| MINIO_SECRET_KEY \| MINIO_ENDPOINT_URL` |
| `ERR_005`  | Invalid parameter value weight: `time \| distance` |
| `ERR_006`  | Invalid parameter value mode: `walk \| bike` |
| `ERR_007`  | Invalid parameter value `output_format` |
| `ERR_008`  | Invalid parameter value `output_EPSG` |
| `ERR_009`  | GeoJSON output must use EPSG:4326 |
| `ERR_010`  | Invalid parameter value `network_nodes` |
| `ERR_011`  | Invalid parameter value `network_edges` |
| `ERR_012`  | `network_nodes` and `network_edges` must be specified together |
| `ERR_013`  | Invalid parameter value poi_category_osm: `park \| restaurantcafe \| …` |
| `ERR_014`  | Invalid parameter value `poi_osm_path` |
| `ERR_015`  | Invalid parameter value poi_category_custom_name: `Custom category cannot match OSM category` |
| `ERR_016`  | Invalid parameter value poi_category_custom: `Custom categories count must match CSV categories count` |
| `ERR_017`  | poi_category_custom_csv not found `<poi_category_custom_csv>` |
| `ERR_018`  | poi_category_custom_style requires at least one csv |
| `ERR_019`  | poi_category_custom_style: more styles than csv categories |
| `ERR_020`  | poi_category_custom_style not found |
| `ERR_021`  | Invalid parameter value poi_category_extended: `extended categories count must match CSV categories count` |
| `ERR_022`  | poi_category_extended_csv not found `<poi_category_extended_csv>` |
| `ERR_023`  | poi_category_extended_style requires at least one csv |
| `ERR_024`  | poi_category_extended_style: more styles than csv categories |
| `ERR_025`  | poi_category_extended_style not found |
| `ERR_026`  | Invalid parameter value park_gates_source: `osm \| csv \| road_network \| virtual` |
| `ERR_027`  | park_gates_csv missing or invalid |
| `ERR_028`  | clip_layer not found `<clip_layer>` |
| `ERR_029`  | grid_gpkg not found `<grid_gpkg>` |

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

- **extended_pois**: contains CSV files for extended categories.

- **osm_network**: contains: nodes.csv and edges.csv

```
output_local_path/
├── output/
│   ├── <filename>.{format}
│   ├── <filename>_extended.{format}
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
├── extended_pois/
│   ├── _publish.json                           
└── osm_network/                                   
    ├── edges.csv
    └── nodes.csv

```
---

## Contact

- chiara.savoldi@dedagroup.it  
- martina.forconi@dedagroup.it  

