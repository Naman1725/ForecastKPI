from flask import Flask, request, jsonify
from forecast_service import run_forecast_pipeline

app = Flask(__name__)

@app.route('/forecast', methods=['POST'])
def forecast():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        zip_file = request.files['file']
        if zip_file.filename == '':
            return jsonify({"error": "No selected file"}), 400

        country = request.form.get('country')
        tech = request.form.get('tech')
        zone = request.form.get('zone')
        kpi = request.form.get('kpi')
        forecast_months = request.form.get('forecast_months', '3')

        if not all([country, tech, zone, kpi]):
            return jsonify({"error": "Missing required parameters"}), 400

        try:
            forecast_months = int(forecast_months)
        except ValueError:
            return jsonify({"error": "forecast_months must be 3 or 6"}), 400

        zip_buffer = zip_file.read()
        plot_json, summary, error = run_forecast_pipeline(
            zip_buffer, country, tech, zone, kpi, forecast_months
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify({
            "plot": plot_json,
            "summary": summary
        })

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/test', methods=['GET'])
def test():
    return jsonify({"status": "API is working"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
