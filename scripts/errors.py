import sys
from datetime import datetime
from scripts.logger import logger


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# -----------------------------------------------------------------------------
# ERRORS
# -----------------------------------------------------------------------------


ERRORS = {

    # --------------------------------
    "ERR_001": "parameters.ini not found or invalid",
    "ERR_002": "Missing required parameter",
    "ERR_003": "output_local_path invalid",
    "ERR_004": "Missing required MinIO configuration: MINIO_ACCESS_KEY | MINIO_SECRET_KEY | MINIO_ENDPOINT_URL",
    "ERR_005": "Invalid parameter value weight",
    "ERR_006": "Invalid parameter value mode",
    "ERR_007": "Invalid parameter value poi_category_osm",
    "ERR_008": "Invalid parameter value poi_category_custom_name",
    "ERR_009": "Invalid parameter value poi_category_custom",
    "ERR_010": "Invalid parameter value park_gates_source",
    "ERR_011": "park_gates_csv_path missing or invalid",
    "ERR_012": "poi_category_custom_csv not found",
    "ERR_013": "clip_layer_path not found",
    "ERR_014": "grid_path not found"    
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
    sys.exit(exit_code)
