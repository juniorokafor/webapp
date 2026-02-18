from flask import Flask, request, jsonify, Response
from dotenv import load_dotenv
import os
from model import Metric
from typing import List
from config.config import get_config, setup_logging
import logging
import json
from dataclasses import asdict
from datetime import datetime

load_dotenv()
config = get_config()
setup_logging()
logger = logging.getLogger(__name__)

HOST = os.getenv('HOST')
PORT = os.getenv('PORT')

app = Flask(__name__)

def json_to_metric(metric_dict: dict) -> Metric:
    """Convert JSON dict back to Metric object"""
    return Metric(
        name=metric_dict['name'],
        value=metric_dict['value'],
        collector_type=metric_dict['collector_type'],
        timestamp=metric_dict['timestamp'],
        unit=metric_dict.get('unit')
    )

latest_metrics: List[Metric] = []

@app.route("/")
def home():
    return "Flask server - <a href='/metrics/latest/json'>JSON</a> | <a href='/metrics/latest/objects'>Objects</a>"

@app.route('/api/metrics', methods=['POST'])
def receive_metrics():
    """Receive JSON → convert to Metric objects → store"""
    global latest_metrics

    try:
        metrics_data = request.json
        logger.info(f"Payload: {metrics_data}")

        # Handle your actual payload structure
        if 'metrics' in metrics_data:
            raw_metrics = metrics_data['metrics']
        elif 'data' in metrics_data and 'metrics' in metrics_data['data']:
            raw_metrics = metrics_data['data']['metrics']
        else:
            return jsonify({'error': 'No metrics found in payload'}), 400

        # Convert JSON → List[Metric]
        latest_metrics = [json_to_metric(m) for m in raw_metrics]
        logger.info(f"Stored {len(latest_metrics)} Metric objects")

        return jsonify({
            'status': 'success',
            'count': len(latest_metrics),
            'message': f'Received {len(latest_metrics)} metrics'
        }), 200

    except Exception as e:
        logger.error(f"Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route("/metrics/latest/json")
def latest_metrics_json():
    """ JSON format"""
    if latest_metrics:
        # Convert Metric objects back to clean JSON
        metrics_json = [asdict(m) for m in latest_metrics]
        response_data = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'count': len(latest_metrics),
            'data': metrics_json
        }
        return Response(
            json.dumps(response_data, indent=2),
            mimetype='application/json'
        )
    return jsonify({'message': 'No metrics available yet'}), 404

@app.route("/metrics/latest/objects")
def latest_metrics_objects():
    """ Raw Metric object representation"""
    if latest_metrics:
        # Generate exact Metric(name='...', value=..., ...) format
        metrics_repr = []
        for m in latest_metrics:
            # Format exactly like Metric.__repr__()
            unit_str = f", unit={repr(m.unit)}" if m.unit is not None else ""
            metrics_repr.append(
                f"Metric(name={repr(m.name)}, value={repr(m.value)}, "
                f"collector_type={repr(m.collector_type)}, "
                f"timestamp={repr(m.timestamp)}{unit_str})"
            )

        response_data = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'count': len(latest_metrics),
            'data': metrics_repr
        }

        # Return as JSON (array of strings) OR plain text
        return Response(
            json.dumps(response_data, indent=2),
            mimetype='application/json'
        )

    return jsonify({'message': 'No metrics available yet'}), 404

@app.route("/metrics/latest/text")
def latest_metrics_text():
    """Raw objects as plain text (exact print format)"""
    if latest_metrics:
        metrics_repr = []
        for m in latest_metrics:
            unit_str = f", unit={repr(m.unit)}" if m.unit is not None else ""
            metrics_repr.append(
                f"Metric(name={repr(m.name)}, value={repr(m.value)}, "
                f"collector_type={repr(m.collector_type)}, "
                f"timestamp={repr(m.timestamp)}{unit_str})"
            )
        return Response("\n".join(metrics_repr), mimetype='text/plain')

    return "No metrics available", 404

@app.route("/api/status")
def status():
    return jsonify({"status": "online", "metrics_count": len(latest_metrics)})

if __name__ == "__main__":
    app.run(debug=True, host=HOST, port=PORT)



