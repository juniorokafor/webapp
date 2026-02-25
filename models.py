from sqlalchemy import Column, DateTime, Double, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Source(Base):
    """
    Normalised source / device registry.
    'source' is the natural key (device_id from the payload); source_id is
    the surrogate PK used as the FK target in metric_values.
    """

    __tablename__ = "source"

    source_id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), unique=True, nullable=False)
    collector_type = Column(String(50), nullable=False)

    def __repr__(self) -> str:
        return f"<Source {self.source!r} ({self.collector_type})>"


class MetricDefinition(Base):
    """
    One row per distinct metric name. Owns the unit so it isn't repeated
    across every reading row (3NF: unit is fully dependent on metric_name,
    not on the composite key of metric_values).
    """

    __tablename__ = "metric_definitions"

    metric_def_id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), unique=True, nullable=False)
    unit = Column(String(20), nullable=True)                      # %, GB, bytes, eur …

    def __repr__(self) -> str:
        return f"<MetricDefinition {self.metric_name!r} unit={self.unit!r}>"


class MetricValue(Base):
    """
    One row per metric reading.

    Value storage:
      - Numeric types (int, float) and booleans (True→1.0 / False→0.0)
        go into value_numeric so SQL aggregations work without casting.
      - String types go into value_string.
      - NULL values leave both columns NULL.

    metric_name is intentionally absent here; retrieve it by joining
    metric_definitions to stay in 3NF (it is transitively dependent on
    metric_id through metric_def_id and is therefore not a direct
    attribute of a metric reading).
    """

    __tablename__ = "metric_values"

    metric_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey("source.source_id"), nullable=False)
    metric_def_id = Column(
        Integer, ForeignKey("metric_definitions.metric_def_id"), nullable=False
    )
    captured_at = Column(DateTime, nullable=False)
    value_numeric = Column(Double, nullable=True)
    value_string = Column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_metric_values_def_captured", "metric_def_id", "captured_at"),
        UniqueConstraint("source_id", "metric_def_id", "captured_at",
                         name="uq_metric_values_source_def_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<MetricValue metric_def_id={self.metric_def_id} "
            f"source_id={self.source_id} captured_at={self.captured_at}>"
        )
