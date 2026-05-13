from flask import Flask, request, jsonify, Response, stream_with_context
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
        params = AnalysisParams(**json_data).dict()
    except Exception as e:
        return jsonify({"error": f"Invalid parameters: {str(e)}"}), 400

    def generate():
      
        yield "START\n"

        try:
            with contextlib.redirect_stdout(io.StringIO()):
                params_validated = validate_api_params(params)
                result = run_analysis(params_validated)

            yield json.dumps({
                "status": "ok",
                "result_path": result["result_path"]
            })

        except Exception as e:
            yield json.dumps({
                "error": str(e)
            })

    return Response(
        stream_with_context(generate()),
        mimetype="application/json"
    )



if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True)
