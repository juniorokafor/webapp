import json
import logging
from datetime import datetime

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, select

from database import SessionLocal
from ingestion import ingest_payload
from models import MetricDefinition, MetricValue, Source

bp = Blueprint("routes", __name__)
logger = logging.getLogger(__name__)


def _latest_metrics_query():
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


def _fetch_latest_rows():
    with SessionLocal() as session:
        return session.execute(_latest_metrics_query()).all()


def _json_envelope(data: list) -> Response:
    return Response(
        json.dumps({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "count": len(data),
            "data": data,
        }, indent=2),
        mimetype="application/json",
    )


def _row_to_dict(mv, md, src) -> dict:
    return {
        "name": md.metric_name,
        "value": mv.value_numeric if mv.value_numeric is not None else mv.value_string,
        "collector_type": src.collector_type,
        "device_id": src.source,
        "timestamp": mv.captured_at.isoformat(),
        "unit": md.unit,
    }


def _format_metric_repr(mv, md, src) -> str:
    value = mv.value_numeric if mv.value_numeric is not None else mv.value_string
    unit_str = f", unit={md.unit!r}" if md.unit is not None else ""
    return (
        f"Metric(name={md.metric_name!r}, value={value!r}, "
        f"collector_type={src.collector_type!r}, "
        f"timestamp={mv.captured_at.isoformat()!r}{unit_str})"
    )


@bp.route("/")
def home():
    return (
        "Flask server — "
        "<a href='/metrics/latest/json'>JSON</a> | "
        "<a href='/metrics/latest/objects'>Objects</a>"
        "<a href='/dashboard>Dashboard</a>"
    )


@bp.route("/api/metrics", methods=["POST"])
@bp.route("/ingest", methods=["POST"])
def receive_metrics():
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


@bp.route("/metrics/latest/json")
def latest_metrics_json():
    rows = _fetch_latest_rows()
    if not rows:
        return jsonify({"message": "No metrics available yet"}), 404
    return _json_envelope([_row_to_dict(mv, md, src) for mv, md, src in rows])


@bp.route("/metrics/latest/objects")
def latest_metrics_objects():
    rows = _fetch_latest_rows()
    if not rows:
        return jsonify({"message": "No metrics available yet"}), 404
    return _json_envelope([_format_metric_repr(mv, md, src) for mv, md, src in rows])


@bp.route("/metrics/latest/text")
def latest_metrics_text():
    rows = _fetch_latest_rows()
    if not rows:
        return Response("No metrics available", mimetype="text/plain"), 404
    return Response(
        "\n".join(_format_metric_repr(mv, md, src) for mv, md, src in rows),
        mimetype="text/plain",
    )


@bp.route("/api/status")
def status():
    with SessionLocal() as session:
        metric_count = session.execute(select(func.count()).select_from(MetricValue)).scalar()
        source_count = session.execute(select(func.count()).select_from(Source)).scalar()
    return jsonify({
        "status": "online",
        "sources": source_count,
        "metric_readings": metric_count,
    })
