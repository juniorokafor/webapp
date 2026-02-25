import json
import logging
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from config.config import setup_logging
from ingestion import ingest_payload
from models import Base, MetricDefinition, MetricValue, Source

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

HOST = os.getenv("HOST", "localhost")
PORT = os.getenv("PORT", 5000)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{Path(__file__).parent / 'metrics.db'}"
)
engine = create_engine(DATABASE_URL, echo=False)
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

app = Flask(__name__)


def _latest_metrics_query():
    """
    Return a SELECT that yields (MetricValue, MetricDefinition, Source) rows
    for the most recent reading of every (source, metric_definition) pair.
    """
    subq = (
        select(
            MetricValue.source_id,
            MetricValue.metric_def_id,
            func.max(MetricValue.captured_at).label("max_captured_at"),
        )
        .group_by(MetricValue.source_id, MetricValue.metric_def_id)
        .subquery()
    )
    return (
        select(MetricValue, MetricDefinition, Source)
        .join(MetricDefinition, MetricValue.metric_def_id == MetricDefinition.metric_def_id)
        .join(Source, MetricValue.source_id == Source.source_id)
        .join(
            subq,
            (MetricValue.source_id == subq.c.source_id)
            & (MetricValue.metric_def_id == subq.c.metric_def_id)
            & (MetricValue.captured_at == subq.c.max_captured_at),
        )
        .order_by(MetricValue.captured_at)
    )


def _row_to_dict(mv: MetricValue, md: MetricDefinition, src: Source) -> dict:
    value = mv.value_numeric if mv.value_numeric is not None else mv.value_string
    return {
        "name": md.metric_name,
        "value": value,
        "collector_type": src.collector_type,
        "device_id": src.source,
        "timestamp": mv.captured_at.isoformat(),
        "unit": md.unit,
    }


def _format_metric_repr(mv: MetricValue, md: MetricDefinition, src: Source) -> str:
    value = mv.value_numeric if mv.value_numeric is not None else mv.value_string
    unit_str = f", unit={md.unit!r}" if md.unit is not None else ""
    return (
        f"Metric(name={md.metric_name!r}, value={value!r}, "
        f"collector_type={src.collector_type!r}, "
        f"timestamp={mv.captured_at.isoformat()!r}{unit_str})"
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    return (
        "Flask server — "
        "<a href='/metrics/latest/json'>JSON</a> | "
        "<a href='/metrics/latest/objects'>Objects</a>"
    )


@app.route("/api/metrics", methods=["POST"])
@app.route("/ingest", methods=["POST"])
def receive_metrics():
    """Receive a metrics payload, persist it, and return an insert count."""
    payload = request.get_json(force=True)

    if payload is None:
        return jsonify({"error": "Invalid JSON body"}), 400
    if "metrics" not in payload:
        return jsonify({"error": "No metrics found in payload"}), 400

    logger.info(f"Received payload with {len(payload['metrics'])} metrics")

    try:
        with SessionLocal() as session:
            inserted = ingest_payload(payload, session)
        logger.info(f"Inserted {inserted} metric rows")
        return jsonify({"status": "success", "inserted": inserted}), 201
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/metrics/latest/json")
def latest_metrics_json():
    """Latest reading per metric, returned as a JSON array."""
    with SessionLocal() as session:
        rows = session.execute(_latest_metrics_query()).all()

    if not rows:
        return jsonify({"message": "No metrics available yet"}), 404

    data = [_row_to_dict(mv, md, src) for mv, md, src in rows]
    body = json.dumps(
        {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "count": len(data),
            "data": data,
        },
        indent=2,
    )
    return Response(body, mimetype="application/json")


@app.route("/metrics/latest/objects")
def latest_metrics_objects():
    """Latest reading per metric, formatted as Metric(...) object strings."""
    with SessionLocal() as session:
        rows = session.execute(_latest_metrics_query()).all()

    if not rows:
        return jsonify({"message": "No metrics available yet"}), 404

    reprs = [_format_metric_repr(mv, md, src) for mv, md, src in rows]
    body = json.dumps(
        {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "count": len(reprs),
            "data": reprs,
        },
        indent=2,
    )
    return Response(body, mimetype="application/json")


@app.route("/metrics/latest/text")
def latest_metrics_text():
    """Latest reading per metric as plain text, one Metric(...) per line."""
    with SessionLocal() as session:
        rows = session.execute(_latest_metrics_query()).all()

    if not rows:
        return Response("No metrics available", mimetype="text/plain"), 404

    lines = [_format_metric_repr(mv, md, src) for mv, md, src in rows]
    return Response("\n".join(lines), mimetype="text/plain")


@app.route("/api/status")
def status():
    with SessionLocal() as session:
        metric_count = session.execute(select(func.count()).select_from(MetricValue)).scalar()
        source_count = session.execute(select(func.count()).select_from(Source)).scalar()
    return jsonify({
        "status": "online",
        "sources": source_count,
        "metric_readings": metric_count,
    })


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
        host=HOST,
        port=int(PORT),
    )
