import logging

import dash
import dash_bootstrap_components as dbc
from dash import callback_context, dcc, html
from dash.dependencies import Input, Output, State
from sqlalchemy import desc, select

from config.config import THEME
from control_ws import hub
from dashboard_utils import (
    build_gauge,
    build_line_chart,
    build_text_card,
    empty_figure,
    get_session,
)
from models import MetricDefinition, MetricValue, Source

logger = logging.getLogger(__name__)


def create_dashboard(server):
    """Create and configure the Dash app for the performance dashboard.
    Args: server: The Flask server instance to attach the Dash app to."""
    dash_app = dash.Dash(
        __name__,
        server=server,
        url_base_pathname="/dashboard/",
        external_stylesheets=[dbc.themes.DARKLY, dbc.icons.BOOTSTRAP],
    )

    dash_app.layout = html.Div([
        html.Div([
            html.Div([
                html.Span(className="live-dot me-2"),
                html.Span("LIVE METRICS DASHBOARD", className="header-title"),
            ], className="d-flex align-items-center"),
            html.Span("System Performance Monitor", className="header-sub"),
        ], className="top-header"),
        html.Div([
            html.Div([
                html.Div("DEVICE", className="control-label mt-3"),
                dbc.Select(id="device-dropdown", placeholder="Select device...", className="mb-4"),
                html.Div("METRIC", className="control-label"),
                dbc.Select(id="metric-dropdown", placeholder="Select metric...", className="mb-4"),
                html.Hr(className="sidebar-divider"),
                html.Div("CURRENT VALUE", className="control-label mt-3"),
                html.Div([
                    html.Span("-", className="stat-value"),
                ], id="current-value-display", className="stat-block"),
                html.Hr(className="sidebar-divider"),
                html.Div("UPLOAD INTERVAL (SECONDS)", className="control-label mt-3"),
                dbc.Input(
                    id="interval-override-input",
                    type="number",
                    min=1,
                    step=1,
                    placeholder="e.g. 15",
                    className="mb-2",
                ),
                dbc.Button("Set Interval", id="set-interval-btn", color="success", className="w-100 mb-2", n_clicks=0),
                dbc.Button("Pause Agent", id="pause-btn", color="warning", className="w-100 mb-2", n_clicks=0),
                dbc.Button("Resume Agent", id="resume-btn", color="info", className="w-100 mb-2", n_clicks=0),
                dbc.Button("Restart Agent", id="restart-btn", color="danger", className="w-100 mb-2", n_clicks=0),
                html.Div(
                    "Commands are sent through WebSocket to the selected device.",
                    id="control-status",
                    style={"fontSize": "12px", "color": THEME["muted"]},
                ),
            ], className="sidebar-panel px-3 py-3"),
            html.Div([
                html.Div([
                    html.I(className="bi bi-activity mb-3", style={"fontSize": "40px", "color": THEME["muted"]}),
                    html.P("Select a device and metric to view data", style={"color": THEME["muted"], "fontSize": "14px"}),
                ], id="empty-state", className="empty-state"),
                html.Div(
                    dcc.Graph(
                        id="gauge",
                        style={"height": "100%"},
                        config={"displaylogo": False, "modeBarButtonsToRemove": ["select2d", "lasso2d"]},
                    ),
                    id="graph-container",
                    style={"display": "none", "height": "100%"},
                ),
            ], className="main-panel p-4"),
        ], className="body-row"),
        dcc.Interval(id="interval", interval=3000, n_intervals=0),
        # interval component to trigger periodic refreshes every 3 seconds
    ], className="app-wrapper")

    @dash_app.callback(
        Output("device-dropdown", "options"),
        Input("interval", "n_intervals"),
    ) # Update device list every 3 seconds, the reaction to dcc.interval

    def load_devices(_): # the _ is the value passed to the callback, its unused as we only need the trigger not the value
        """Load the list of available devices from the database."""
        with get_session() as session:
            devices = session.execute(select(Source)).scalars().all()
            # this retrieves all rows from the Source table and converts them to a list of Source objects
            hostname_rows = session.execute(
                select(MetricValue.source_id, MetricValue.value_string)
                .join(MetricDefinition, MetricValue.metric_def_id == MetricDefinition.metric_def_id)
                # match rows where metric_def_id is the same in both tables
                .where(MetricDefinition.metric_name == "system_info.hostname")
            ).all()

        hostname_map = {row.source_id: row.value_string for row in hostname_rows}
        return [{"label": hostname_map.get(d.source_id, d.source), "value": str(d.source_id)} for d in devices]

    @dash_app.callback(
        Output("metric-dropdown", "options"),
        Input("device-dropdown", "value"),
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

        return [{"label": m.metric_name, "value": str(m.metric_def_id)} for m in metrics]

    @dash_app.callback(
        Output("control-status", "children"),
        Input("set-interval-btn", "n_clicks"),
        Input("pause-btn", "n_clicks"),
        Input("resume-btn", "n_clicks"),
        Input("restart-btn", "n_clicks"),
        State("device-dropdown", "value"),
        State("interval-override-input", "value"),
        prevent_initial_call=True,
    )
    def send_command(_, __, ___, ____, source_id, interval_value):
        if not source_id:
            return "Select a device first."

        with get_session() as session:
            source = session.execute(
                select(Source).where(Source.source_id == int(source_id))
            ).scalar_one_or_none()

        if source is None:
            return "Selected device no longer exists."

        device_id = source.source
        triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]

        command = ""
        payload = {}
        if triggered_id == "set-interval-btn":
            try:
                interval = int(interval_value)
            except (TypeError, ValueError):
                return "Interval must be a whole number."
            if interval < 1:
                return "Interval must be at least 1 second."
            command = "set_interval"
            payload = {"upload_interval_seconds": interval}
        elif triggered_id == "pause-btn":
            command = "pause"
        elif triggered_id == "resume-btn":
            command = "resume"
        elif triggered_id == "restart-btn":
            command = "restart"
        else:
            return "Unknown command trigger."

        try:
            ack = hub.send_command(device_id=device_id, command=command, payload=payload, timeout=6)
            if not ack.get("ok", False):
                return f"Device responded with error: {ack.get('message', 'unknown error')}"
            return f"Command sent to {device_id}: {ack.get('message', 'ok')}"
        except Exception as e:
            logger.warning("Failed sending WS command to %s: %s", device_id, e)
            detail = str(e) or e.__class__.__name__
            return f"Failed to send command: {detail}"

    def _stat_font_size(text):
        n = len(str(text))
        if n <= 7:
            return "44px"
        if n <= 10:
            return "32px"
        if n <= 14:
            return "22px"
        return "16px"

    @dash_app.callback(
        Output("gauge", "figure"),
        Output("graph-container", "style"),
        Output("empty-state", "style"),
        Output("current-value-display", "children"),
        Input("interval", "n_intervals"),
        Input("device-dropdown", "value"),
        Input("metric-dropdown", "value"),
    )
    def update_chart(_, source_id, metric_def_id):
        _chart_hidden = {"display": "none", "height": "100%"}
        _chart_visible = {"display": "block", "height": "100%"}
        _empty_visible = {"display": "flex"}
        _empty_hidden = {"display": "none"}
        _no_value = [html.Span("-", className="stat-value")]

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

            if latest.value_string is not None:
                val_display = [html.Span(latest.value_string, className="stat-value-text")]
                return (
                    build_text_card(metric_def.metric_name, latest.value_string),
                    _chart_visible,
                    _empty_hidden,
                    val_display,
                )

            if metric_def.unit == "%":
                val_str = f"{latest.value_numeric:.1f}"
                val_display = [
                    html.Span(val_str, className="stat-value", style={"fontSize": _stat_font_size(val_str)}),
                    html.Span("%", className="stat-unit"),
                ]
                return (
                    build_gauge(metric_def.metric_name, latest.value_numeric, latest.captured_at),
                    _chart_visible,
                    _empty_hidden,
                    val_display,
                )

            rows = session.execute(
                select(MetricValue)
                .where(MetricValue.source_id == sid, MetricValue.metric_def_id == mid)
                .order_by(desc(MetricValue.captured_at))
                .limit(100)
            ).scalars().all()

        unit = metric_def.unit or ""
        val_str = f"{latest.value_numeric:.2f}"
        val_display = [
            html.Span(val_str, className="stat-value", style={"fontSize": _stat_font_size(val_str)}),
            html.Span(f" {unit}", className="stat-unit"),
        ]

        return (
            build_line_chart(metric_def.metric_name, metric_def.unit, rows[::-1]),
            _chart_visible,
            _empty_hidden,
            val_display,
        )

    return dash_app
