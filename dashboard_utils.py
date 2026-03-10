from html import escape
import plotly.graph_objects as go
from contextlib import contextmanager
from database import SessionLocal
from config.config import (
    ANNO, FONT_MONO, FONT_UI, HIDDEN_AXES, LABEL_SIZE, RGBA_ACCENT_5, RGBA_ACCENT_7,
    RGBA_DANGER_5, RGBA_WARNING_5, THEME, TICK_SIZE,
)
"""Plotly figure building
helper functions for the dashboard."""

def stat_font_size(text):
    """Return a CSS font-size string that scales down as the text gets longer."""
    n = len(str(text))
    if n <= 7:  return "44px"
    if n <= 10: return "32px"
    if n <= 14: return "22px"
    return "16px"


def _axis_style(title):
    """Return a styled axis config dict for the line chart."""
    return {
        "title": {"text": title, "font": {"color": THEME["muted"], "size": TICK_SIZE}},
        "gridcolor": THEME["border"],
        "color": THEME["muted"],
        "showgrid": True,
        "zeroline": False,
        "tickfont": {"size": TICK_SIZE},
    }


@contextmanager
def get_session():
    """
    Provide a safe SQLAlchemy session for dashboard callbacks.
    Ensures sessions are always closed properly.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------- Shared layout defaults ----------

def _base_layout(**overrides):
    """
    Base layout used by all dashboard charts so they share
    the same theme and styling. Extra kwargs are forwarded directly to Plotly.
    """
    return dict(
        paper_bgcolor=THEME["surface"],
        plot_bgcolor=THEME["bg"],
        font={"family": FONT_UI, "color": THEME["text"]},
        margin={"l": 24, "r": 24, "t": 40, "b": 24},
        **overrides,
    )


def empty_figure():
    """Return an empty Plotly figure used as a placeholder when there is no data."""
    fig = go.Figure()
    fig.update_layout(**_base_layout(), **HIDDEN_AXES)
    return fig


# ---------- Figure Builders ----------

def _wrap_lines(text, width=45):
    """Split text into a list of lines no longer than `width` chars.
    This function ensures that long values in text cards are wrapped 
    and don't overflow the card boundaries."""
    words, lines, current = text.split(), [], ""
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines or [""]


def build_text_card(metric_name, value):
    """Build a text card with a metric name and value."""
    lines = _wrap_lines(str(value))
    n = len(lines)
    font_size = 28 if n == 1 else 20 if n <= 3 else 14

    # Space lines evenly; cap step so they never crowd
    step = min(0.14, 0.65 / max(n, 1))
    block_top = 0.5 + (n - 1) * step / 2

    fig = go.Figure()

    # Metric name sits above the value block
    fig.add_annotation(
        text=escape(metric_name).upper(),
        x=0.5, y=block_top + step * 1.4,
        font={"size": LABEL_SIZE, "color": THEME["muted"], "family": FONT_UI},
        align="center",
        **ANNO,
    )

    for i, line in enumerate(lines):
        fig.add_annotation(
            text=escape(line),
            x=0.5, y=block_top - i * step,
            font={"size": font_size, "color": THEME["accent"], "family": FONT_MONO},
            align="center",
            **ANNO,
        )

    fig.update_layout(**_base_layout(), **HIDDEN_AXES)

    return fig


def build_gauge(metric_name, value, timestamp):
    """Build a gauge chart for a percentage metric."""
    val = value or 0

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        title={"text": metric_name.upper(),
               "font": {"color": THEME["muted"], "size": LABEL_SIZE}},
        number={"font": {"color": THEME["accent"], "size": 52, "family": FONT_MONO},
                "suffix": "%"},
        gauge={
            "axis": {
                "range": [0, 100],
                "tickcolor": THEME["muted"],
                "tickfont": {"color": THEME["muted"], "size": TICK_SIZE},
                "tickwidth": 1,
            },
            "bar": {"color": THEME["accent"], "thickness": 0.2},
            "bgcolor": THEME["bg"],
            "borderwidth": 0,
            "steps": [
                {"range": [0, 60],   "color": RGBA_ACCENT_5},
                {"range": [60, 80],  "color": RGBA_WARNING_5},
                {"range": [80, 100], "color": RGBA_DANGER_5},
            ],
            "threshold": {
                "line": {"color": THEME["danger"], "width": 2},
                "thickness": 0.75,
                "value": 90,
            },
        }
    ))

    fig.add_annotation(
        text=timestamp.strftime("updated %H:%M:%S"),
        x=0.5, y=-0.08,
        font={"size": LABEL_SIZE, "color": THEME["muted"]},
        **ANNO,
    )

    fig.update_layout(**_base_layout())

    return fig


def build_line_chart(metric_name, unit, rows):
    """Build a line chart for a time series metric."""
    # extract timestamps and metric values
    times = [r.captured_at for r in rows]
    values = [r.value_numeric for r in rows]

    unit_label = unit or "value"

    fig = go.Figure(go.Scatter(
        x=times,
        y=values,
        mode="lines+markers",
        line={"color": THEME["accent"], "width": 2, "shape": "spline", "smoothing": 0.5},
        marker={"color": THEME["accent"], "size": 4},
        fill="tozeroy",
        fillcolor=RGBA_ACCENT_7,
        hovertemplate=f"<b>%{{y:.2f}} {escape(unit_label)}</b><br>%{{x|%H:%M:%S}}<extra></extra>",
    ))

    fig.update_layout(
        **_base_layout(),
        title={
            "text": metric_name.upper(),
            "font": {"color": THEME["muted"], "size": LABEL_SIZE},
            "x": 0,
            "xanchor": "left",
        },
        xaxis=_axis_style("TIME"),
        yaxis=_axis_style(unit_label.upper()),
        hoverlabel={
            "bgcolor": THEME["surface"],
            "bordercolor": THEME["border"],
            "font": {"color": THEME["text"], "size": 13},
        },
    )

    return fig
