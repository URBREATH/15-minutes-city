import sys
from datetime import datetime
from scripts.logger import logger


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# -----------------------------------------------------------------------------
# ERRORS
# -----------------------------------------------------------------------------


ERRORS = {
    # --- Generic / Execution ---
    "ERR_001": "parameters.ini not found or invalid",
    "ERR_002": "Missing required parameter",
    "ERR_003": "output_local_path invalid",
    "ERR_004": "Missing required MinIO configuration: MINIO_ACCESS_KEY | MINIO_SECRET_KEY | MINIO_ENDPOINT_URL",
    "ERR_005": "Invalid parameter value weight",
    "ERR_006": "Invalid parameter value mode",
    "ERR_007": "Invalid parameter value output_format",
    "ERR_008": "Invalid parameter value output_EPSG",
    "ERR_009": "GeoJSON output must use EPSG:4326",

    # --- Network ---
    "ERR_010": "Invalid parameter value network_nodes",
    "ERR_011": "Invalid parameter value network_edges",
    "ERR_012": "network_nodes and network_edges must be specified together",

    # --- POI OSM ---
    "ERR_013": "Invalid parameter value poi_category_osm",
    "ERR_014": "Invalid parameter value poi_osm_path",

    # --- POI custom ---
    "ERR_015": "custom category cannot match OSM category",
    "ERR_016": "custom categories count must match CSV categories count",
    "ERR_017": "poi_category_custom_csv not found",
    "ERR_018": "poi_category_custom_style requires at least one csv",
    "ERR_019": "poi_category_custom_style: more styles than csv categories",
    "ERR_020": "poi_category_custom_style not found",

    # --- POI complementary ---
    "ERR_021": "complementary categories count must match CSV categories count",
    "ERR_022": "poi_category_complementary_csv not found",
    "ERR_023": "poi_category_complementary_style requires at least one csv",
    "ERR_024": "poi_category_complementary_style: more styles than csv categories",
    "ERR_025": "poi_category_complementary_style not found",

    # --- Park ---
    "ERR_026": "Invalid parameter value park_gates_source",
    "ERR_027": "park_gates_csv missing or invalid",

    # --- Grid ---
    "ERR_028": "clip_layer not found",
    "ERR_029": "grid_gpkg not found",
}

# -----------------------------------------------------------------------------
# MAIN ERROR FUNCTION
# -----------------------------------------------------------------------------
def raise_error(code, extra=None, exit_code=1):

# code: error code defined in ERRORS dictionary.
# extra: Additional contextual information (file path, value, etc.).
# exit_code : System exit code (default = 1).


    # Retrieve message from catalog
    message = ERRORS.get(code, "Unknown error")

    # Build extra details string
    details = []

    if extra:
        details.append(str(extra))

    detail_str = " | ".join(details)

    logger.info("--------------------------------------------------------------------------------")
    if detail_str:
        logger.info(f"[{ts()}] {code} {message}: {detail_str}")
    else:
        logger.info(f"[{ts()}] {code} {message}")    

    logger.info("--------------------------------------------------------------------------------")

    # Stop script execution
    sys.exit(f"{code}: {message}" + (f" | {extra}" if extra else ""))
