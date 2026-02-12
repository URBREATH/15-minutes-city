from flask import Flask, request, jsonify
import io
import contextlib
from overallExecutor import run_analysis
from pydantic import BaseModel
from typing import List, Optional

app = Flask(__name__)

class AnalysisParams(BaseModel):
    bbox: List[float]
    outputPath: str
    weight: str = "time"
    category: str = "all"
    by: str = "foot"
    flag_or: bool = False
    flag_post_download: str = "a"
    gate_path: Optional[str] = None
    clip_layer_path: Optional[str] = None
    city_name: Optional[str] = None

@app.route('/execute', methods=['POST'])
def execute():
    try:
        json_data = request.get_json()
        # Validazione e conversione dei parametri
        params = AnalysisParams(**json_data).dict()
    except Exception as e:
        return jsonify({"error": f"Invalid parameters: {str(e)}"}), 400
    
    # Capture the stdout
    output_buffer = io.StringIO()
    with contextlib.redirect_stdout(output_buffer):
        try:
            run_analysis(params)
        except Exception as e:
            # Even if the script fails, we capture the output
            print(f"An error occurred during execution: {e}")

    output = output_buffer.getvalue()
    
    return output, 200

if __name__ == '__main__':
    app.run(threaded=True)
