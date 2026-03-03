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


# ---------- Shared layout defaults ----------

def _base_layout(**overrides):
    return dict(
        paper_bgcolor=THEME["surface"],
        plot_bgcolor=THEME["bg"],
        font={"family": "Inter, Segoe UI, sans-serif", "color": THEME["text"]},
        margin={"l": 24, "r": 24, "t": 40, "b": 24},
        **overrides,
    )


# ---------- Empty Figure ----------

def empty_figure():
    fig = go.Figure()
    fig.update_layout(
        **_base_layout(),
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    return fig


# ---------- Figure Builders ----------

def _wrap_lines(text, width=45):
    """Split text into a list of lines no longer than `width` chars."""
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
        xref="paper", yref="paper",
        x=0.5, y=block_top + step * 1.4,
        showarrow=False,
        font={"size": 11, "color": THEME["muted"], "family": "Inter, sans-serif"},
        align="center",
    )

    for i, line in enumerate(lines):
        fig.add_annotation(
            text=escape(line),
            xref="paper", yref="paper",
            x=0.5, y=block_top - i * step,
            showarrow=False,
            font={"size": font_size, "color": THEME["accent"],
                  "family": "JetBrains Mono, monospace"},
            align="center",
        )

    fig.update_layout(
        **_base_layout(),
        xaxis={"visible": False},
        yaxis={"visible": False},
    )

    return fig


def build_gauge(metric_name, value, timestamp):
    val = value or 0
    bar_color = THEME["accent"]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        title={"text": metric_name.upper(),
               "font": {"color": THEME["muted"], "size": 11}},
        number={"font": {"color": THEME["accent"], "size": 52,
                         "family": "JetBrains Mono, monospace"},
                "suffix": "%"},
        gauge={
            "axis": {
                "range": [0, 100],
                "tickcolor": THEME["muted"],
                "tickfont": {"color": THEME["muted"], "size": 10},
                "tickwidth": 1,
            },
            "bar": {"color": bar_color, "thickness": 0.2},
            "bgcolor": THEME["bg"],
            "borderwidth": 0,
            "steps": [
                {"range": [0, 60],   "color": "rgba(34, 197, 94, 0.05)"},
                {"range": [60, 80],  "color": "rgba(240, 160, 64, 0.05)"},
                {"range": [80, 100], "color": "rgba(224, 80, 80, 0.05)"},
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
        xref="paper", yref="paper",
        x=0.5, y=-0.08,
        showarrow=False,
        font={"size": 11, "color": THEME["muted"]},
    )

    fig.update_layout(**_base_layout())

    return fig


def build_line_chart(metric_name, unit, rows):
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
        fillcolor="rgba(34, 197, 94, 0.07)",
        hovertemplate=f"<b>%{{y:.2f}} {escape(unit_label)}</b><br>%{{x|%H:%M:%S}}<extra></extra>",
    ))

    fig.update_layout(
        **_base_layout(),
        title={
            "text": metric_name.upper(),
            "font": {"color": THEME["muted"], "size": 11},
            "x": 0,
            "xanchor": "left",
        },
        xaxis={
            "title": {"text": "TIME", "font": {"color": THEME["muted"], "size": 10}},
            "gridcolor": THEME["border"],
            "color": THEME["muted"],
            "showgrid": True,
            "zeroline": False,
            "tickfont": {"size": 10},
        },
        yaxis={
            "title": {"text": unit_label.upper(), "font": {"color": THEME["muted"], "size": 10}},
            "gridcolor": THEME["border"],
            "color": THEME["muted"],
            "showgrid": True,
            "zeroline": False,
            "tickfont": {"size": 10},
        },
        hoverlabel={
            "bgcolor": THEME["surface"],
            "bordercolor": THEME["border"],
            "font": {"color": THEME["text"], "size": 13},
        },
    )

    return fig
