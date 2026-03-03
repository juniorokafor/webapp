import dash
import dash_bootstrap_components as dbc
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
        url_base_pathname="/dashboard/",
        external_stylesheets=[dbc.themes.DARKLY, dbc.icons.BOOTSTRAP],
    )

    # ---------- Layout ----------

    dash_app.layout = html.Div([

        # Top header bar
        html.Div([
            html.Div([
                html.Span(className="live-dot me-2"),
                html.Span("LIVE METRICS DASHBOARD", className="header-title"),
            ], className="d-flex align-items-center"),
            html.Span("System Performance Monitor", className="header-sub"),
        ], className="top-header"),

        # Body
        html.Div([

            # Sidebar
            html.Div([

                html.Div("DEVICE", className="control-label mt-3"),
                dbc.Select(id="device-dropdown", placeholder="Select device...", className="mb-4"),

                html.Div("METRIC", className="control-label"),
                dbc.Select(id="metric-dropdown", placeholder="Select metric...", className="mb-4"),

                html.Hr(className="sidebar-divider"),

                html.Div("CURRENT VALUE", className="control-label mt-3"),
                html.Div([
                    html.Span("—", className="stat-value"),
                ], id="current-value-display", className="stat-block"),

            ], className="sidebar-panel px-3 py-3"),

            # Main chart area
            html.Div([

                # Empty state
                html.Div([
                    html.I(className="bi bi-activity mb-3", style={"fontSize": "40px", "color": THEME["muted"]}),
                    html.P("Select a device and metric to view data",
                           style={"color": THEME["muted"], "fontSize": "14px"}),
                ], id="empty-state", className="empty-state"),

                # Chart
                html.Div(
                    dcc.Graph(
                        id="gauge",
                        style={"height": "100%"},
                        config={"displaylogo": False,
                                "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
                    ),
                    id="graph-container",
                    style={"display": "none", "height": "100%"},
                ),

            ], className="main-panel p-4"),

        ], className="body-row"),

        dcc.Interval(id="interval", interval=3000, n_intervals=0),

    ], className="app-wrapper")

    # ---------- Device Dropdown ----------

    @dash_app.callback(
        Output("device-dropdown", "options"),
        Input("interval", "n_intervals")
    )
    def load_devices(_):

        with get_session() as session:

            devices = session.execute(select(Source)).scalars().all()

            hostname_rows = session.execute(
                select(MetricValue.source_id, MetricValue.value_string)
                .join(MetricDefinition, MetricValue.metric_def_id == MetricDefinition.metric_def_id)
                .where(MetricDefinition.metric_name == "system_info.hostname")
            ).all()

        hostname_map = {row.source_id: row.value_string for row in hostname_rows}

        return [
            {"label": hostname_map.get(d.source_id, d.source), "value": str(d.source_id)}
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
            metrics = session.execute(
                select(MetricDefinition)
                .join(MetricValue)
                .where(MetricValue.source_id == int(source_id))
                .distinct()
            ).scalars().all()

        return [
            {"label": m.metric_name, "value": str(m.metric_def_id)}
            for m in metrics
        ]

    # ---------- Helpers ----------

    def _stat_font_size(text):
        n = len(str(text))
        if n <= 7:  return "44px"
        if n <= 10: return "32px"
        if n <= 14: return "22px"
        return "16px"

    # ---------- Chart Update ----------

    @dash_app.callback(
        Output("gauge", "figure"),
        Output("graph-container", "style"),
        Output("empty-state", "style"),
        Output("current-value-display", "children"),
        Input("interval", "n_intervals"),
        Input("device-dropdown", "value"),
        Input("metric-dropdown", "value")
    )
    def update_chart(_, source_id, metric_def_id):

        _chart_hidden  = {"display": "none",  "height": "100%"}
        _chart_visible = {"display": "block", "height": "100%"}
        _empty_visible = {"display": "flex"}
        _empty_hidden  = {"display": "none"}
        _no_value      = [html.Span("—", className="stat-value")]

        if not source_id or not metric_def_id:
            return empty_figure(), _chart_hidden, _empty_visible, _no_value

        sid = int(source_id)
        mid = int(metric_def_id)

        with get_session() as session:

            metric_def = session.execute(
                select(MetricDefinition).where(MetricDefinition.metric_def_id == mid)
            ).scalar_one_or_none()

            if not metric_def:
                return empty_figure(), _chart_hidden, _empty_visible, _no_value

            latest = session.execute(
                select(MetricValue)
                .where(MetricValue.source_id == sid, MetricValue.metric_def_id == mid)
                .order_by(desc(MetricValue.captured_at))
                .limit(1)
            ).scalar_one_or_none()

            if not latest:
                return empty_figure(), _chart_hidden, _empty_visible, _no_value

            # ---------- String Value ----------

            if latest.value_string is not None:
                val_display = [html.Span(latest.value_string, className="stat-value-text")]
                return (
                    build_text_card(metric_def.metric_name, latest.value_string),
                    _chart_visible, _empty_hidden, val_display
                )

            # ---------- Gauge ----------

            if metric_def.unit == "%":
                val_str = f"{latest.value_numeric:.1f}"
                val_display = [
                    html.Span(val_str, className="stat-value",
                              style={"fontSize": _stat_font_size(val_str)}),
                    html.Span("%", className="stat-unit"),
                ]
                return (
                    build_gauge(metric_def.metric_name, latest.value_numeric, latest.captured_at),
                    _chart_visible, _empty_hidden, val_display
                )

            # ---------- Line Chart ----------

            rows = session.execute(
                select(MetricValue)
                .where(MetricValue.source_id == sid, MetricValue.metric_def_id == mid)
                .order_by(desc(MetricValue.captured_at))
                .limit(100)
            ).scalars().all()

        unit = metric_def.unit or ""
        val_str = f"{latest.value_numeric:.2f}"
        val_display = [
            html.Span(val_str, className="stat-value",
                      style={"fontSize": _stat_font_size(val_str)}),
            html.Span(f" {unit}", className="stat-unit"),
        ]

        return (
            build_line_chart(metric_def.metric_name, metric_def.unit, rows[::-1]),
            _chart_visible, _empty_hidden, val_display
        )

    return dash_app
