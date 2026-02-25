from html import escape
import plotly.graph_objects as go
from contextlib import contextmanager
from database import SessionLocal
from config.config import THEME

# ---------- Session Helper ----------

@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------- Empty Figure ----------
def empty_figure():
    return go.Figure()


# ---------- Figure Builders ----------

def build_text_card(metric_name, value):

    fig = go.Figure(go.Table(
        header=dict(
            values=[f"<b>{escape(metric_name)}</b>"],
            fill_color="#2c2c2c",
            font={"size": 13, "color": THEME["text"]},
            align="center",
            height=40,
        ),
        cells=dict(
            values=[[escape(str(value))]],
            fill_color=THEME["surface"],
            font={"size": 24, "color": THEME["text"]},
            align="center",
            height=80,
        )
    ))

    fig.update_layout(
        margin={"l": 20, "r": 20, "t": 20, "b": 20},
        paper_bgcolor=THEME["surface"],
    )

    return fig


def build_gauge(metric_name, value, timestamp):

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value or 0,
        title={"text": metric_name, "font": {"color": THEME["text"]}},
        number={"font": {"color": THEME["text"]}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": THEME["muted"]},
            "bar": {"color": THEME["accent"]},
            "bgcolor": "#2c2c2c",
            "bordercolor": "#3a3a3a",
        }
    ))

    fig.add_annotation(
        text=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.0,
        showarrow=False,
        font={"size": 12, "color": THEME["muted"]},
    )

    fig.update_layout(
        paper_bgcolor=THEME["surface"],
        font={"color": THEME["text"]},
    )

    return fig


def build_line_chart(metric_name, unit, rows):

    times = [r.captured_at for r in rows]
    values = [r.value_numeric for r in rows]

    fig = go.Figure(go.Scatter(
        x=times,
        y=values,
        mode="lines+markers",
        line={"color": THEME["accent"]},
        marker={"color": THEME["accent"]},
    ))

    fig.update_layout(
        title={"text": metric_name, "font": {"color": THEME["text"]}},
        xaxis_title="Time",
        yaxis_title=unit or "Value",
        paper_bgcolor=THEME["surface"],
        plot_bgcolor=THEME["bg"],
        font={"color": THEME["text"]},
        xaxis={"gridcolor": "#2c2c2c", "color": THEME["muted"]},
        yaxis={"gridcolor": "#2c2c2c", "color": THEME["muted"]},
    )

    return fig