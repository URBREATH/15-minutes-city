from flask import Flask, request, jsonify
import io
import contextlib 
from main_15min import run_analysis
import os
import json
from scripts.errors import raise_error
from scripts.validate import validate_api_params
from scripts.model import AnalysisParams
app = Flask(__name__)


    

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
            params = validate_api_params(params)
       
            run_analysis(params)
        except Exception as e:
            print(f"An error occurred during execution: {e}")

    output = output_buffer.getvalue()
    
    return output, 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
