import dash
from dash import dcc, html
from dash.dependencies import Input, Output
from sqlalchemy import select, desc

from models import MetricValue, MetricDefinition, Source
from config.config import THEME
from dashboard_utils import (empty_figure, build_text_card, build_gauge,
                             get_session, build_line_chart)

# ---------- Dashboard ----------

def create_dashboard(server):

    dash_app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname="/dashboard/"
    )

    # ---------- Layout ----------

    dash_app.layout = html.Div([

        html.H2(
    "Live Metrics Dashboard",
    style={
        "color": THEME["text"],
        "marginBottom": "24px",
        "letterSpacing": "1px",
        "fontWeight": "600"
    }
),

        html.Label(
    "Select Device",
    style={
        "color": THEME["muted"],
        "fontSize": "13px",
        "marginBottom": "6px",
        "display": "block"
    }
),

        dcc.Dropdown(
    id="device-dropdown",
    style={
        "marginBottom": "16px",
        "backgroundColor": THEME["surface"],
        "color": THEME["text"]
    }
),

        html.Label(
            "Select Metric",
            style={
        "color": THEME["muted"],
        "fontSize": "13px",
        "marginBottom": "6px",
        "display": "block"
    }
        ),

        dcc.Dropdown(
    id="metric-dropdown",
    style={
        "marginBottom": "24px",
        "backgroundColor": THEME["surface"],
        "color": THEME["text"]
    }
),

        html.Div(

    dcc.Graph(
        id="gauge",
        style={"height": "420px"}
    ),

    id="graph-container",
    style={
        "display": "none",
        "backgroundColor": THEME["surface"],
        "padding": "20px",
        "borderRadius": "12px",
        "boxShadow": "0 4px 12px rgba(0,0,0,0.4)",
        "border": "1px solid #2c2c2c",
        "marginTop": "10px"
    }
),

        dcc.Interval(
            id="interval",
            interval=3000,
            n_intervals=0
        )

    ], style={

        "backgroundColor": THEME["bg"],
        "minHeight": "100vh",
        "padding": "40px 60px",
        "maxWidth": "960px",
        "margin": "0 auto",
        "boxSizing": "border-box",
    })

    # ---------- Device Dropdown ----------

    @dash_app.callback(
        Output("device-dropdown", "options"),
        Input("interval", "n_intervals")
    )
    def load_devices(_):

        with get_session() as session:

            devices = session.execute(
                select(Source)
            ).scalars().all()

            hostname_stmt = (
                select(
                    MetricValue.source_id,
                    MetricValue.value_string
                )
                .join(
                    MetricDefinition,
                    MetricValue.metric_def_id == MetricDefinition.metric_def_id
                )
                .where(
                    MetricDefinition.metric_name == "system_info.hostname"
                )
            )

            hostname_rows = session.execute(hostname_stmt).all()

        hostname_map = {
            row.source_id: row.value_string
            for row in hostname_rows
        }

        return [
            {
                "label": hostname_map.get(d.source_id, d.source),
                "value": d.source_id
            }
            for d in devices
        ]

    # ---------- Metric Dropdown ----------

    @dash_app.callback(
        Output("metric-dropdown", "options"),
        Input("device-dropdown", "value")
    )
    def load_metrics(source_id):

        if not source_id:
            return []

        with get_session() as session:

            stmt = (
                select(MetricDefinition)
                .join(MetricValue)
                .where(MetricValue.source_id == source_id)
                .distinct()
            )

            metrics = session.execute(stmt).scalars().all()

        return [
            {
                "label": m.metric_name,
                "value": m.metric_def_id
            }
            for m in metrics
        ]

    # ---------- Chart Update ----------

    _container_hidden = {"display": "none", "backgroundColor": THEME["surface"], "padding": "20px", "borderRadius": "12px", "boxShadow": "0 4px 12px rgba(0,0,0,0.4)", "border": "1px solid #2c2c2c", "marginTop": "10px"}
    _container_visible = {**_container_hidden, "display": "block"}

    @dash_app.callback(
        Output("gauge", "figure"),
        Output("graph-container", "style"),
        Input("interval", "n_intervals"),
        Input("device-dropdown", "value"),
        Input("metric-dropdown", "value")
    )
    def update_chart(_, source_id, metric_def_id):

        if not source_id or not metric_def_id:
            return empty_figure(), _container_hidden

        with get_session() as session:

            metric_def = session.execute(
                select(MetricDefinition)
                .where(
                    MetricDefinition.metric_def_id == metric_def_id
                )
            ).scalar_one_or_none()

            if not metric_def:
                return empty_figure(), _container_hidden

            latest = session.execute(
                select(MetricValue)
                .where(
                    MetricValue.source_id == source_id,
                    MetricValue.metric_def_id == metric_def_id
                )
                .order_by(desc(MetricValue.captured_at))
                .limit(1)
            ).scalar_one_or_none()

            if not latest:
                return empty_figure(), _container_hidden

            # ---------- String Value ----------

            if latest.value_string is not None:

                return build_text_card(
                    metric_def.metric_name,
                    latest.value_string
                ), _container_visible

            # ---------- Gauge ----------

            if metric_def.unit == "%":

                return build_gauge(
                    metric_def.metric_name,
                    latest.value_numeric,
                    latest.captured_at
                ), _container_visible

            # ---------- Line Chart ----------

            rows = session.execute(
                select(MetricValue)
                .where(
                    MetricValue.source_id == source_id,
                    MetricValue.metric_def_id == metric_def_id
                )
                .order_by(desc(MetricValue.captured_at))
                .limit(100)
            ).scalars().all()

        rows = rows[::-1]

        return build_line_chart(
            metric_def.metric_name,
            metric_def.unit,
            rows
        ), _container_visible

    return dash_app