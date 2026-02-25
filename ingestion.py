import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import MetricDefinition, MetricValue, Source

logger = logging.getLogger(__name__)


def _to_value_columns(value: Any) -> tuple[float | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, bool):
        return float(value), None
    if isinstance(value, (int, float)):
        return float(value), None
    return None, str(value)


def _get_or_create(session: Session, model, filter_col, filter_val, **kwargs):
    obj = session.execute(
        select(model).where(filter_col == filter_val)
    ).scalar_one_or_none()

    if obj is None:
        try:
            with session.begin_nested():
                obj = model(**kwargs)
                session.add(obj)
                session.flush()
        except IntegrityError:
            obj = session.execute(
                select(model).where(filter_col == filter_val)
            ).scalar_one()

    return obj


def ingest_payload(payload: dict, session: Session) -> int:
    inserted = 0
    source_cache: dict[str, Source] = {}
    def_cache: dict[str, MetricDefinition] = {}

    for i, raw in enumerate(payload["metrics"]):
        try:
            device_id: str = raw["device_id"]
            metric_name: str = raw["name"]

            if device_id not in source_cache:
                source_cache[device_id] = _get_or_create(
                    session, Source, Source.source, device_id,
                    source=device_id, collector_type=raw["collector_type"],
                )

            if metric_name not in def_cache:
                metric_def = _get_or_create(
                    session, MetricDefinition, MetricDefinition.metric_name, metric_name,
                    metric_name=metric_name, unit=raw.get("unit"),
                )
                if metric_def.unit != raw.get("unit"):
                    logger.warning(
                        f"Unit mismatch for {metric_name!r}: "
                        f"stored={metric_def.unit!r}, received={raw.get('unit')!r}"
                    )
                def_cache[metric_name] = metric_def

            value_numeric, value_string = _to_value_columns(raw["value"])

            session.add(MetricValue(
                source_id=source_cache[device_id].source_id,
                metric_def_id=def_cache[metric_name].metric_def_id,
                captured_at=datetime.fromisoformat(raw["timestamp"]),
                value_numeric=value_numeric,
                value_string=value_string,
            ))
            inserted += 1

        except (KeyError, ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed metric at index {i}: {e} — entry: {raw}")

    session.commit()
    return inserted
