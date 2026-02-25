import html as html_lib
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

    SURFACE = "#1e1e1e"
    BG = "#121212"
    TEXT = "#e0e0e0"
    MUTED = "#aaaaaa"
    ACCENT = "#4a9eff"

    # ---- Layout ----
    dash_app.layout = html.Div([
        html.H2(
            "Live Metrics Dashboard",
            style={"color": TEXT, "marginBottom": "24px", "letterSpacing": "1px"}
        ),

        html.Label("Select Device", style={"color": MUTED, "fontSize": "12px", "marginBottom": "4px"}),
        dcc.Dropdown(
            id="device-dropdown",
            style={"marginBottom": "16px"}
        ),

        html.Label("Select Metric", style={"color": MUTED, "fontSize": "12px", "marginBottom": "4px"}),
        dcc.Dropdown(
            id="metric-dropdown",
            style={"marginBottom": "24px"}
        ),

        dcc.Graph(
            id="gauge",
            style={"borderRadius": "8px", "overflow": "hidden"}
        ),

        dcc.Interval(
            id="interval",
            interval=3000,
            n_intervals=0
        )
    ], style={
        "backgroundColor": BG,
        "minHeight": "100vh",
        "padding": "40px 60px",
        "maxWidth": "960px",
        "margin": "0 auto",
        "boxSizing": "border-box",
    })

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

    # ---- Update Chart ----
    @dash_app.callback(
        Output("gauge", "figure"),
        Input("interval", "n_intervals"),
        Input("device-dropdown", "value"),
        Input("metric-dropdown", "value")
    )
    def update_chart(_, device_source, metric_def_id):

        if not device_source or not metric_def_id:
            return go.Figure()

        session = SessionLocal()

        source = session.execute(
            select(Source).where(Source.source == device_source)
        ).scalar_one_or_none()

        if not source:
            session.close()
            return go.Figure()

        metric_def = session.execute(
            select(MetricDefinition).where(MetricDefinition.metric_def_id == metric_def_id)
        ).scalar_one_or_none()

        if not metric_def:
            session.close()
            return go.Figure()

        latest = session.execute(
            select(MetricValue)
            .where(
                MetricValue.source_id == source.source_id,
                MetricValue.metric_def_id == metric_def_id
            )
            .order_by(desc(MetricValue.captured_at))
            .limit(1)
        ).scalar_one_or_none()

        if not latest:
            session.close()
            return go.Figure()

        SURFACE = "#1e1e1e"
        BG = "#121212"
        TEXT = "#e0e0e0"
        MUTED = "#aaaaaa"
        ACCENT = "#4a9eff"

        # String / boolean → text card
        if latest.value_string is not None:
            session.close()
            fig = go.Figure(go.Table(
                header=dict(
                    values=[f"<b>{html_lib.escape(metric_def.metric_name)}</b>"],
                    fill_color="#2c2c2c",
                    font={"size": 13, "color": TEXT},
                    align="center",
                    height=40,
                ),
                cells=dict(
                    values=[[html_lib.escape(str(latest.value_string))]],
                    fill_color=SURFACE,
                    font={"size": 24, "color": TEXT},
                    align="center",
                    height=80,
                )
            ))
            fig.update_layout(
                margin={"l": 20, "r": 20, "t": 20, "b": 20},
                paper_bgcolor=SURFACE,
            )
            return fig

        # Percentage → gauge
        if metric_def.unit == "%":
            session.close()
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=latest.value_numeric or 0,
                title={"text": metric_def.metric_name, "font": {"color": TEXT}},
                number={"font": {"color": TEXT}},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": MUTED},
                    "bar": {"color": ACCENT},
                    "bgcolor": "#2c2c2c",
                    "bordercolor": "#3a3a3a",
                }
            ))
            fig.add_annotation(
                text=latest.captured_at.strftime("%Y-%m-%d %H:%M:%S"),
                xref="paper", yref="paper",
                x=0.5, y=0.0,
                showarrow=False,
                font={"size": 12, "color": MUTED}
            )
            fig.update_layout(
                paper_bgcolor=SURFACE,
                font={"color": TEXT},
            )
            return fig

        # All other numeric (crypto prices, bytes, etc.) → line graph
        rows = session.execute(
            select(MetricValue)
            .where(
                MetricValue.source_id == source.source_id,
                MetricValue.metric_def_id == metric_def_id
            )
            .order_by(MetricValue.captured_at)
            .limit(100)
        ).scalars().all()
        session.close()

        times = [r.captured_at for r in rows]
        values = [r.value_numeric for r in rows]

        fig = go.Figure(go.Scatter(
            x=times,
            y=values,
            mode="lines+markers",
            line={"color": ACCENT},
            marker={"color": ACCENT},
        ))
        fig.update_layout(
            title={"text": metric_def.metric_name, "font": {"color": TEXT}},
            xaxis_title="Time",
            yaxis_title=metric_def.unit or "Value",
            paper_bgcolor=SURFACE,
            plot_bgcolor=BG,
            font={"color": TEXT},
            xaxis={"gridcolor": "#2c2c2c", "color": MUTED},
            yaxis={"gridcolor": "#2c2c2c", "color": MUTED},
        )
        return fig

    return dash_app