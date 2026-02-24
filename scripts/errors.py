import sys
from datetime import datetime


def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# -----------------------------------------------------------------------------
# ERRORS
# -----------------------------------------------------------------------------


ERRORS = {

    # --------------------------------
    "ERR_001": "parameters.ini not found or invalid",
    "ERR_002": "Missing required parameter",
    "ERR_003": "outputPath invalid",
    "ERR_004": "Invalid parameter value weight",
    "ERR_005": "Invalid parameter value mode",
    "ERR_006": "Invalid parameter value poi_category_osm",
    "ERR_007": "Invalid parameter value poi_category_custom_name",
    "ERR_008": "Invalid parameter value poi_category_custom",
    "ERR_009": "Invalid parameter value park_gates_source",
    "ERR_010": "park_gates_csv_path missing or invalid",
    "ERR_011": "poi_category_custom_csv not found",
    "ERR_012": "clip_layer_path not found",
    "ERR_013": "grid_path not found"    
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

    print("--------------------------------------------------------------------------------", flush=True)
    if detail_str:
        print(f"[{ts()}] {code} {message}: {detail_str}", flush=True)
    else:
        print(f"[{ts()}] {code} {message}", flush=True)    

    print("--------------------------------------------------------------------------------", flush=True)

    # Stop script execution
    sys.exit(exit_code)
