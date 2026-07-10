from flask import Flask, request, jsonify
from main_15min import run_analysis
from scripts.validate import validate_api_params
from pydantic import BaseModel, Field
from typing import Optional, List


class AOI(BaseModel):
    bbox: List[float]


class Execution(BaseModel):
    output_local_path: str
    output_minio_path: Optional[str] = None
    filename: str = None
    weight: Optional[str] = "time"
    mode: Optional[str] = "walk"
    walk_speed_kmh: Optional[float] = 5.0
    bike_speed_kmh: Optional[float] = 15.0
    output_format: Optional[str] = "gpkg"
    output_epsg: Optional[int] = 3857


class Network(BaseModel):
    network_edges: Optional[str] = None
    network_nodes: Optional[str] = None


class POI(BaseModel):
    poi_category_osm: Optional[str] = None
    poi_osm_path: Optional[str] = None
    poi_category_custom_name: Optional[str] = None
    poi_category_custom_csv: Optional[str] = None
    poi_category_custom_style: Optional[str] = None
    poi_category_extended_name: Optional[str] = None
    poi_category_extended_csv: Optional[str] = None
    poi_category_extended_style: Optional[str] = None

class Park(BaseModel):
    park_gates_source: Optional[str] = None
    park_gates_osm_buffer_m: Optional[float] = 10.0
    park_gates_csv: Optional[str] = None
    park_gates_virtual_distance_m: float = 100.0


class Grid(BaseModel):
    grid_gpkg: Optional[str] = None
    hex_diameter_m: Optional[int] = 250
    clip_layer: Optional[str] = None
    virtual_nodes: Optional[str] = "false"


class AnalysisParams(BaseModel):
    aoi: AOI
    execution: Execution
    network: Network = Field(default_factory=Network)
    poi: POI = Field(default_factory=POI)
    park: Park = Field(default_factory=Park)
    grid: Grid = Field(default_factory=Grid)
    
    
app = Flask(__name__)

@app.route('/execute', methods=['POST'])
def execute():
    try:
        json_data = request.get_json()
        params = AnalysisParams(**json_data).dict()
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Invalid parameters: {str(e)}"
        }), 400

    try:
        params_validated = validate_api_params(params)
        result = run_analysis(params_validated)

        return jsonify({
            "status": "ok",
            "result_path": result["result_path"]
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
