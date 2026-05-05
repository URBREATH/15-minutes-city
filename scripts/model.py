from pydantic import BaseModel, Field
from typing import Optional, List

class AOI(BaseModel):
    bbox: List[float]


class Execution(BaseModel):
    output_local_path: str
    output_minio_path: Optional[str] = None
    filename: str = None
    weight: str = "time"
    mode: str = "walk"
    walk_speed_kmh: float = 5.0
    bike_speed_kmh: float = 15.0   
    output_format: str = "gpkg"
    output_EPSG: str = "3857"



class POI(BaseModel):
    poi_category_osm: Optional[str] = None
    poi_category_custom_name: Optional[str] = None
    poi_category_custom_csv: Optional[str] = None
    poi_category_custom_style: Optional[str] = None


class Park(BaseModel):
    park_gates_source: Optional[str] = None
    park_gates_osm_buffer_m: Optional[float] = 10.0
    park_gates_csv: Optional[str] = None
    park_gates_virtual_distance_m: Optional[float] = 100.0


class Grid(BaseModel):
    grid_gpkg: Optional[str] = None
    hex_diameter_m: Optional[int] = 250
    clip_layer: Optional[str] = None


class AnalysisParams(BaseModel):
    aoi: AOI
    execution: Execution
    poi: POI = Field(default_factory=POI)
    park: Park = Field(default_factory=Park)
    grid: Grid = Field(default_factory=Grid)
