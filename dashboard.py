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

    # ---- Layout ----
    dash_app.layout = html.Div([
        html.H2("Live Metrics Dashboard"),

        html.Label("Select Device"),
        dcc.Dropdown(id="device-dropdown"),

        html.Label("Select Metric"),
        dcc.Dropdown(id="metric-dropdown"),

        dcc.Graph(id="gauge"),

        dcc.Interval(
            id="interval",
            interval=500,
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

        # String / boolean → text card
        if latest.value_string is not None:
            session.close()
            fig = go.Figure(go.Table(
                header=dict(
                    values=[f"<b>{html_lib.escape(metric_def.metric_name)}</b>"],
                    fill_color="lightgrey",
                    font={"size": 13},
                    align="center",
                    height=40,
                ),
                cells=dict(
                    values=[[html_lib.escape(str(latest.value_string))]],
                    font={"size": 24},
                    align="center",
                    height=80,
                )
            ))
            fig.update_layout(margin={"l": 20, "r": 20, "t": 20, "b": 20})
            return fig

        # Percentage → gauge
        if metric_def.unit == "%":
            session.close()
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=latest.value_numeric or 0,
                title={"text": metric_def.metric_name},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "blue"},
                }
            ))
            fig.add_annotation(
                text=latest.captured_at.strftime("%Y-%m-%d %H:%M:%S"),
                xref="paper", yref="paper",
                x=0.5, y=0.0,
                showarrow=False,
                font={"size": 12, "color": "gray"}
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
        ))
        fig.update_layout(
            title=metric_def.metric_name,
            xaxis_title="Time",
            yaxis_title=metric_def.unit or "Value",
        )
        return fig

    return dash_app