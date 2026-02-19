"""
Reconstruct metric objects from a raw payload and persist them to the DB.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import MetricDefinition, MetricValue, Source


def _to_value_columns(value: Any) -> tuple[float | None, str | None]:
    """
    Map a raw Python value to (value_numeric, value_string).

    Booleans are checked before int/float because bool is a subclass of int
    in Python; they are stored as 1.0 / 0.0 so SQL aggregations work.
    """
    if value is None:
        return None, None
    if isinstance(value, bool):
        return float(value), None      # True → 1.0, False → 0.0
    if isinstance(value, (int, float)):
        return float(value), None
    return None, str(value)


def _get_or_create_source(session: Session, device_id: str, collector_type: str) -> Source:
    source = session.execute(
        select(Source).where(Source.source == device_id)
    ).scalar_one_or_none()

    if source is None:
        source = Source(source=device_id, collector_type=collector_type)
        session.add(source)
        session.flush()  # populate source_id

    return source


def _get_or_create_metric_def(session: Session, metric_name: str, unit: str | None) -> MetricDefinition:
    metric_def = session.execute(
        select(MetricDefinition).where(MetricDefinition.metric_name == metric_name)
    ).scalar_one_or_none()

    if metric_def is None:
        metric_def = MetricDefinition(metric_name=metric_name, unit=unit)
        session.add(metric_def)
        session.flush()  # populate metric_def_id

    return metric_def


def ingest_payload(payload: dict, session: Session) -> int:
    """
    Parse a raw metrics payload and persist all readings.
    Returns the number of MetricValue rows inserted.
    """
    inserted = 0

    # Cache lookups within this payload to avoid redundant DB round-trips
    source_cache: dict[str, Source] = {}
    def_cache: dict[str, MetricDefinition] = {}

    for raw in payload["metrics"]:
        device_id: str = raw["device_id"]
        metric_name: str = raw["name"]

        if device_id not in source_cache:
            source_cache[device_id] = _get_or_create_source(
                session, device_id, raw["collector_type"]
            )

        if metric_name not in def_cache:
            def_cache[metric_name] = _get_or_create_metric_def(
                session, metric_name, raw.get("unit")
            )

        value_numeric, value_string = _to_value_columns(raw["value"])

        session.add(MetricValue(
            source_id=source_cache[device_id].source_id,
            metric_def_id=def_cache[metric_name].metric_def_id,
            captured_at=datetime.fromisoformat(raw["timestamp"]),
            value_numeric=value_numeric,
            value_string=value_string,
        ))
        inserted += 1

    session.commit()
    return inserted
