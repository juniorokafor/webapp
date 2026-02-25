import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
from sqlalchemy import select, desc
from database import SessionLocal
from models import MetricValue, MetricDefinition, Source


def create_dashboard(server):

    dash_app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname="/dashboard/"
    )

    # ---- Layout ----
    dash_app.layout = html.Div([
        html.H2("Live Metric Gauge"),

        html.Label("Select Device"),
        dcc.Dropdown(id="device-dropdown"),

        html.Label("Select Metric"),
        dcc.Dropdown(id="metric-dropdown"),

        dcc.Graph(id="gauge"),

        dcc.Interval(
            id="interval",
            interval=3000,  # 3 seconds
            n_intervals=0
        )
    ])

    # ---- Populate Device Dropdown ----
    @dash_app.callback(
        Output("device-dropdown", "options"),
        Input("interval", "n_intervals")
    )
    def load_devices(_):
        session = SessionLocal()
        devices = session.execute(select(Source)).scalars().all()

        # Look up the hostname metric for each source
        hostname_stmt = (
            select(MetricValue.source_id, MetricValue.value_string)
            .join(MetricDefinition, MetricValue.metric_def_id == MetricDefinition.metric_def_id)
            .where(MetricDefinition.metric_name == "system_info.hostname")
        )
        hostname_rows = session.execute(hostname_stmt).all()
        session.close()

        hostname_map = {row.source_id: row.value_string for row in hostname_rows}

        return [
            {"label": hostname_map.get(d.source_id, d.source), "value": d.source}
            for d in devices
        ]

    # ---- Populate Metric Dropdown ----
    @dash_app.callback(
        Output("metric-dropdown", "options"),
        Input("device-dropdown", "value")
    )
    def load_metrics(device_source):
        if not device_source:
            return []

        session = SessionLocal()

        source = session.execute(
            select(Source).where(Source.source == device_source)
        ).scalar_one_or_none()

        if not source:
            session.close()
            return []

        stmt = (
            select(MetricDefinition)
            .join(MetricValue)
            .where(MetricValue.source_id == source.source_id)
            .distinct()
        )

        metrics = session.execute(stmt).scalars().all()
        session.close()

        return [
            {"label": m.metric_name, "value": m.metric_def_id}
            for m in metrics
        ]

    # ---- Update Gauge ----
    @dash_app.callback(
        Output("gauge", "figure"),
        Input("interval", "n_intervals"),
        Input("device-dropdown", "value"),
        Input("metric-dropdown", "value")
    )
    def update_gauge(_, device_source, metric_def_id):

        if not device_source or not metric_def_id:
            return go.Figure()

        session = SessionLocal()

        source = session.execute(
            select(Source).where(Source.source == device_source)
        ).scalar_one_or_none()

        if not source:
            session.close()
            return go.Figure()

        stmt = (
            select(MetricValue)
            .where(
                MetricValue.source_id == source.source_id,
                MetricValue.metric_def_id == metric_def_id
            )
            .order_by(desc(MetricValue.captured_at))
            .limit(1)
        )

        result = session.execute(stmt).scalar_one_or_none()
        session.close()

        value = result.value_numeric if result else 0

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=value or 0,
            title={"text": "Current Value"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "blue"},
            }
        ))

        return fig

    return dash_app