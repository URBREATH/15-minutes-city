# 15-minutes-city
Open-source tool for 15-minute city analysis

## Overview and Purpose

The **15-Minute City algorithm** is designed to assign a proximity index to urban services within a defined geographic area. It evaluates how easily residents can access Points of Interest (PoIs) on foot or by bicycle, following the “15-minute city” concept introduced by **Carlos Moreno**.  
This urban planning model envisions that most daily needs should be met within a 15-minute walk or bike ride from home.

The primary goal of the algorithm is to **quantify accessibility** to essential urban services in a manner that is both globally applicable and locally detailed.  
To ensure broad usability and replicability, the algorithm relies exclusively on **open-source, freely available data**, primarily sourced from **OpenStreetMap (OSM)**.

---

## Key Features
- The tool uses either **OpenStreetMap (OSM)** or **local data** as its data source.
- Measures accessibility to **8 categories of urban services (POIs):**
  - Market and groceries (`marketgroc`)
  - Restaurants and cafés (`restaurantcafe`)
  - Education (`education`)
  - Health (`health`)
  - Banks and post offices (`postbank`)
  - Parks (`park`)
  - Entertainment (`entertainment`)
  - Shops (`shop`)
- Calculates travel time to services by walking or biking.
- Supports both **external and OSM-derived gates** for park access.
---

## Algorithm Workflow

### 1. Data Download

1. A dedicated folder is created for the target geographic area.  
2. If the folder already exists, the process does not overwrite it, preserving previous work.  
3. Key spatial parameters (area size in lat/lon and representative radius) are computed and stored in a CSV file (unique_bbox.csv).  
4. The street network is downloaded from OSM, restricted to pedestrian- or bicycle-accessible streets, depending on the selected mode of travel.  
5. PoIs corresponding to the selected service categories are retrieved.

---

### 2. Hexagonal Grid Generation

- The study area is divided into **hexagonal tiles** with a diameter of 250 m (side = 125 m), generated only where OSM street nodes exist.  
- Hexagons provide an optimal balance between **spatial resolution** and **computational efficiency**.

---

### 3. Proximity Index Calculation

For each hexagon:

1. Travel times to the nearest PoI in each service category are calculated; the model uses network-based accessibility calculations implemented through the **Pandana library** to find the nearest POI for each location. 
2. Only streets accessible by the chosen mode (foot or bike) are considered.
3. The walking time used is **5 km/h**.
4. An average travel time (`overall_average`)  across all categories is computed (sum of POI minutes divided by the number of categories).  
5. Each hexagon is assigned a value (`overall_max`) based on the maximum travel time

**Outputs:**

- **CSV (EPSG:3857)** containing:
  - Travel times for each service category  
  - Average travel time  
  - `overall_max` index  
- **GPKG file** clipped to administrative boundaries of the area for spatial visualization and GIS analysis.

---
### 4. Park Access Point Classification

All service categories are represented as point features in OSM, except for parks. For parks, park gates are used as points.
Each park is assigned access points classified into three types:

- **Type A** – Existing gates Points located within 10 m of the park boundary, identified using the following OSM tags:

o barrier = gate
o barrier = gate
o barrier = entrance
o entrance = yes
o leisure = park
o leisure = dog_park

- **Type B** – Street–park intersections If no Type A gates are found, the tool identifies intersections between the park perimeter and the street network, using any OSM street tagged as:

o 'highway'='primary' or 'highway'='primary_link' or 'highway'='secondary' or 'highway'='secondary_link' or 'highway'='tertiary' or 'highway'='tertiary_link' or 'highway'='unclassified' or 'highway'='residential' or 'bicycle_road'='yes' or 'bicycle'='designated' or 'highway'='living_street' or 'highway'='pedestrian' or 'highway'='service' or 'service'='parking_aisle' or 'highway'='escape' or 'highway'='road' or 'highway'='track' or 'highway'='path' or 'highway'='bus_guideway' or 'highway'='footway' or 'highway'='cycleway' or 'highway'='passing_place' or 'cycleway'='lane' or 'cycleway'='track' or 'highway'='steps'

- **Type C** – Virtual access points If no Type A or B points are available, the tool generates virtual gates every 100 m along the park perimeter.

### 4. Park Gate Management (POIs)

The algorithm manages **park access points (gates)** as follows:

- Supports external gates via CSV or automatically downloaded OSM gates.  
- Flexible processing based on `flag_post_download`:

| Mode | Behavior |
|------|-----------|
| **AS_IS** | Save gates as they are |
| **ONLY_A** | Keep only gates within 10 m of park perimeter |
| **A_B_C** | Classify gates into: A,B,C |

**Workflow:**

1. If `flag_or=True`, gates are read from the external CSV.  
2. If `flag_or=False`, gates and parks are retrieved from OSM.  
3. Gates are processed according to `flag_post_download`.  
4. Final gates are saved to: outputPath_bbox/poi/park.csv.


---

### 5. QGIS Headless Implementation

The algorithm uses **QGIS in offscreen mode** to perform all geospatial computations.  
Initialization includes:
- Importing QGIS and Python libraries  
- Setting environment variables for headless operation  
- Initializing the QGIS application and Processing framework

---

### 6. Parameter Handling

The script reads a `.ini` configuration file to dynamically configure inputs.

**Example (`parameter.ini`):**

```ini
[common]
bbox = 
outputPath = 
weight = time
category = all
by = foot
flag_or = 
flag_post_download = 
gate_path =
clip_layer_path = 
city_name = 
```

Parameters include bounding box, output folder, travel mode (always 'time'), category (usually 'all'), by (for us 'foot') and gate management flags.

**bbox**: bounding box → defines the area of interest where the index is computed (specified as [lat_min, lon_min, lat_max, lon_max])
**category**: service category for which the index is calculated (one of 8 categories ['marketgroc','restaurantcafe','education','health','postbank','park','entertainment','shop'] or 'all' for a combined score)
**by**: mode of transportation considered (pedestrian or cycling, default = 'foot’ or 'bike')
**weight**: measurement criterion  → criterion used for accessibility computation (time or distance)
**clip_layer_path**: boundary polygon → polygon used to limit or clip the area of interest (e.g., administrative borders, district boundaries..)
**outputPath**: output folder → folder where output files and results will be stored
**gate_path**:  gate folder → folder where gates are places in case of external gates
**city_name**: name of the city for which the index is calculates

Read using the read_param function, which preserves key case and converts Python literals.

Allows the script to run fully configured via .ini without modifying the code.

### 7. Technical Implementation

**Programming Language:** Python

**Libraries:**
Pandana, geopandas, numpy, pandas, osmnet, rtree, pyproj, shapely,
geovoronoi, fiona=1.9.5, rasterio, gdal, scipy, beautifulsoup, from qgis.core import *

**Input Data:** OSM network and PoIs, divided into 8 categories

**Output Data:** CSV and GPKG files with travel times, proximity averages, and categorical accessibility (overall_max)

Execution: Command line or IDE:
```ini
.../python3 overallExecutor.py parameters.ini > log.txt 2>&1 &
```

It is necessary to specify the correct path of the python instance. This command runs the Python script overallExecutor.py in the background, redirecting both standard output and error messages to the file log.txt.


### 8. Main Scripts
1.	**overallExecutor.py**

This is the main workflow script for the 15-Minute City Proximity Index. Its main responsibilities are:
o	Parameter handling: Reads configuration from a .ini.
o	Perform each step by calling the functions contained in utilityScript.py.
o	Logging and timing: Prints progress and timing for each step.

2.	**utilityScript.py**

Contains helper functions used by overallExecutor.py:
o	Bounding box preparation
o	Data download: Downloads street networks and Points of Interest (PoIs) from OpenStreetMap, filtered by mode of transport (walking or biking) and category. 
o	Proximity computation: Calls computo to calculate travel times to PoIs for each hexagonal tile and computes the proximity index according to the 15-minute city rules.
o	Output saving: Uses save_output to merge results and save CSV and GIS files for further analysis.

3.	**gates_green_Areas.py**

Manages park access points (gates) for “green areas”.

4.	**parameters.py**

Provides functions for reading input parameters from .ini file.
