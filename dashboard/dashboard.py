"""FAHHH? companion dashboard (Plotly Dash).

Live view of the device for a companion or station staff:
device online/offline, current state, distance, battery and an event log.
Data comes from MQTT (contracts/C3_mqtt.md); every message is also logged
to dashboard/data/messages_<timestamp>.csv for the test evidence.

Run:
    python dashboard.py            # then open http://127.0.0.1:8050
    python fake_publisher.py       # in a second terminal, if the ESP32 isn't running
"""

import argparse
from datetime import datetime, timedelta

import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

from subscriber import TelemetryStore, new_log_path, start_subscriber

WINDOW_MIN = 5          # charts show the last 5 minutes
REFRESH_MS = 1000

# Colours (reference palette: status set + series blue). Status colours always
# come with an icon and a label, never colour alone.
C = {
    "surface": "#fcfcfb", "card": "#ffffff", "border": "#e6e5e0",
    "text": "#0b0b0b", "text2": "#52514e", "muted": "#8a8984", "grid": "#ecebe7",
    "series": "#2a78d6",
    "good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b",
    "neutral": "#8a8984",
}
STATES = {  # state -> (colour, icon, label)
    "NORMAL": (C["good"], "●", "Normal"),
    "GUIDING": (C["series"], "➜", "Guiding"),
    "WARNING": (C["warning"], "▲", "Warning"),
    "EMERGENCY": (C["critical"], "■", "Emergency"),
    "ERROR": (C["neutral"], "✕", "Sensor error"),
}
EVENTS = {  # event -> (marker symbol, label)
    "LEVEL_CHANGE": ("triangle-up", "Level change"),
    "BOARDING_GAP": ("diamond", "Boarding gap"),
    "GUIDE_STEP": ("circle", "Guide step"),
    "ARRIVED_PLATFORM": ("star", "Arrived at platform"),
    "EMERGENCY": ("square", "Emergency"),
    "SENSOR_ERROR": ("x", "Sensor error"),
    "LOW_BATTERY": ("triangle-down", "Low battery"),
}
FONT = "-apple-system, BlinkMacSystemFont, 'Inter', 'Helvetica Neue', Arial, sans-serif"


def state_style(state):
    return STATES.get(state, (C["neutral"], "?", state.title() if state else "Unknown"))


def base_layout(fig, y_title, y_range=None):
    fig.update_layout(
        margin=dict(l=56, r=16, t=8, b=36), height=260,
        paper_bgcolor=C["card"], plot_bgcolor=C["card"],
        font=dict(family=FONT, size=13, color=C["text2"]),
        hovermode="x unified", showlegend=False,
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=C["border"], font=dict(color=C["text"])),
        uirevision="keep",  # keep zoom between refreshes
    )
    fig.update_xaxes(showgrid=False, linecolor=C["border"], tickformat="%H:%M:%S",
                     showspikes=True, spikemode="across", spikethickness=1, spikecolor=C["muted"], spikedash="solid")
    fig.update_yaxes(title_text=y_title, gridcolor=C["grid"], zeroline=False, linecolor=C["border"], range=y_range)
    return fig


def empty_fig(y_title, message):
    fig = base_layout(go.Figure(), y_title)
    fig.add_annotation(text=message, showarrow=False, font=dict(color=C["muted"], size=14),
                       xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def distance_figure(status, events, since):
    pts = [s for s in status if s["_t"] >= since]
    if not pts:
        return empty_fig("Distance (cm)", "Waiting for data…")
    fig = base_layout(go.Figure(), "Distance (cm)", [0, 320])
    fig.add_trace(go.Scatter(
        x=[p["_t"] for p in pts], y=[p["distance_cm"] for p in pts], mode="lines",
        line=dict(color=C["series"], width=2), name="Distance", connectgaps=False,
        hovertemplate="%{y:.0f} cm<extra>Distance</extra>",
    ))
    for name, (symbol, label) in EVENTS.items():
        evs = [e for e in events if e["event"] == name and e["_t"] >= since]
        if not evs:
            continue
        fig.add_trace(go.Scatter(
            x=[e["_t"] for e in evs], y=[e["distance_cm"] if e["distance_cm"] is not None else 0 for e in evs],
            mode="markers", name=label,
            marker=dict(symbol=symbol, size=12, color=[state_style(e["state"])[0] for e in evs],
                        line=dict(color=C["card"], width=2)),
            hovertemplate=f"{label}<extra></extra>",
        ))
    return fig


def battery_figure(status, since):
    pts = [s for s in status if s["_t"] >= since]
    if not pts:
        return empty_fig("Battery (%)", "Waiting for data…")
    fig = base_layout(go.Figure(), "Battery (%)", [0, 105])
    fig.add_trace(go.Scatter(
        x=[p["_t"] for p in pts], y=[p["battery"] for p in pts], mode="lines",
        line=dict(color=C["series"], width=2), name="Battery",
        hovertemplate="%{y}%<extra>Battery</extra>",
    ))
    fig.add_hline(y=20, line=dict(color=C["muted"], width=1, dash="dot"),
                  annotation_text="Low battery 20%", annotation_font_color=C["text2"],
                  annotation_position="top left")
    return fig


def pill(text, colour, icon):
    return html.Span([html.Span(icon, style={"color": colour, "marginRight": "6px"}), text], style={
        "display": "inline-flex", "alignItems": "center", "padding": "6px 12px", "borderRadius": "999px",
        "background": C["card"], "border": f"1px solid {C['border']}", "fontSize": "14px", "color": C["text"],
    })


def tile(label, value, sub=None, accent=None, icon=None):
    return html.Div([
        html.Div(label, style={"fontSize": "13px", "color": C["text2"], "marginBottom": "6px"}),
        html.Div([html.Span(icon, style={"color": accent, "marginRight": "8px"}) if icon else None, value],
                 style={"fontSize": "28px", "fontWeight": 600, "color": C["text"]}),
        html.Div(sub or " ", style={"fontSize": "13px", "color": C["muted"], "marginTop": "4px"}),
    ], style={"background": C["card"], "border": f"1px solid {C['border']}", "borderRadius": "14px",
              "padding": "16px 18px", "flex": "1 1 180px", "minWidth": "160px"})


def card(title, child):
    return html.Div([
        html.Div(title, style={"fontSize": "15px", "fontWeight": 600, "color": C["text"], "margin": "0 0 8px 4px"}),
        child,
    ], style={"background": C["card"], "border": f"1px solid {C['border']}", "borderRadius": "14px",
              "padding": "14px 14px 8px", "marginTop": "14px"})


def event_legend():
    items = []
    for name, (symbol, label) in EVENTS.items():
        glyph = {"triangle-up": "▲", "diamond": "◆", "circle": "●", "star": "★",
                 "square": "■", "x": "✕", "triangle-down": "▼"}[symbol]
        items.append(html.Span([html.Span(glyph, style={"marginRight": "4px"}), label],
                               style={"marginRight": "14px", "whiteSpace": "nowrap"}))
    return html.Div(items, style={"fontSize": "12px", "color": C["text2"], "margin": "2px 4px 6px",
                                  "display": "flex", "flexWrap": "wrap", "rowGap": "4px"})


def build_app(store):
    app = Dash(__name__, title="FAHHH? Dashboard")
    app.index_string = app.index_string.replace(
        "<head>", f"<head><style>html,body{{margin:0;background:{C['surface']};}}</style>", 1)
    app.layout = html.Div([
        html.Div([
            html.Div([
                html.Div("Team FAHHH? · SIC Batch 8", style={"fontSize": "13px", "color": C["text2"]}),
                html.H1("Companion dashboard", style={"fontSize": "26px", "margin": "2px 0 0", "color": C["text"]}),
            ]),
            html.Div(id="pills", style={"display": "flex", "gap": "8px", "flexWrap": "wrap"}),
        ], style={"display": "flex", "justifyContent": "space-between", "alignItems": "flex-end",
                  "flexWrap": "wrap", "gap": "12px"}),
        html.Div(id="tiles", style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginTop": "16px"}),
        card("Distance ahead (last 5 min)", html.Div([
            event_legend(),
            dcc.Graph(id="distance", config={"displaylogo": False}),
        ])),
        card("Battery (last 5 min)", dcc.Graph(id="battery", config={"displaylogo": False})),
        card("Event log (newest first)", html.Div(id="log")),
        html.Div(id="footer", style={"fontSize": "12px", "color": C["muted"], "margin": "12px 4px"}),
        dcc.Interval(id="tick", interval=REFRESH_MS),
    ], style={"fontFamily": FONT, "background": C["surface"], "minHeight": "100vh",
              "padding": "24px clamp(16px, 4vw, 40px)", "boxSizing": "border-box", "maxWidth": "1200px",
              "margin": "0 auto"})

    @app.callback(
        Output("pills", "children"), Output("tiles", "children"), Output("distance", "figure"),
        Output("battery", "figure"), Output("log", "children"), Output("footer", "children"),
        Input("tick", "n_intervals"),
    )
    def refresh(_):
        snap = store.snapshot()
        status, events = snap["status"], snap["events"]
        since = datetime.now() - timedelta(minutes=WINDOW_MIN)

        # Device is online only if it said so AND status is fresh
        if snap["online"] and not snap["stale"]:
            device = pill("Device online", C["good"], "●")
        elif snap["online"] is False:
            device = pill("Device offline", C["critical"], "■")
        else:
            device = pill("No data", C["neutral"], "○")
        broker = pill("Broker connected" if snap["broker_connected"] else "Broker disconnected",
                      C["good"] if snap["broker_connected"] else C["critical"],
                      "●" if snap["broker_connected"] else "■")
        pills = [device, broker]

        last = status[-1] if status else None
        if last:
            colour, icon, label = state_style(last["state"])
            age = snap["status_age_s"]
            dist = "—" if last["distance_cm"] is None else f"{last['distance_cm']:.0f} cm"
            dist_sub = "no reading (sensor error)" if last["distance_cm"] is None else "to the nearest obstacle / edge"
            recent = [e for e in events if e["_t"] >= since]
            emerg = sum(e["event"] == "EMERGENCY" for e in recent)
            tiles = [
                tile("Current state", label, f"updated {age:.0f} s ago", colour, icon),
                tile("Distance", dist, dist_sub),
                tile("Battery", f"{last['battery']}%", "low" if last["battery"] < 20 else "ok",
                     C["warning"] if last["battery"] < 20 else None, "▲" if last["battery"] < 20 else None),
                tile("Events (last 5 min)", str(len(recent)), f"{emerg} emergency" if emerg == 1 else f"{emerg} emergencies",
                     C["critical"] if emerg else None, "■" if emerg else None),
            ]
        else:
            tiles = [tile("Current state", "—", "waiting for the device"), tile("Distance", "—"),
                     tile("Battery", "—"), tile("Events (last 5 min)", "0")]

        rows = []
        for e in reversed(events[-15:]):
            colour, icon, label = state_style(e["state"])
            rows.append(html.Tr([
                html.Td(e["_t"].strftime("%H:%M:%S")),
                html.Td(EVENTS.get(e["event"], (None, e["event"]))[1]),
                html.Td([html.Span(icon, style={"color": colour, "marginRight": "6px"}), label]),
                html.Td("—" if e["distance_cm"] is None else f"{e['distance_cm']:.0f} cm", style={"textAlign": "right"}),
                html.Td(f"{e['battery']}%", style={"textAlign": "right"}),
            ], style={"borderTop": f"1px solid {C['grid']}"}))
        th = {"textAlign": "left", "fontWeight": 500, "color": C["text2"], "padding": "6px 8px"}
        log = html.Table([
            html.Thead(html.Tr([html.Th("Time", style=th), html.Th("Event", style=th), html.Th("State", style=th),
                                html.Th("Distance", style={**th, "textAlign": "right"}),
                                html.Th("Battery", style={**th, "textAlign": "right"})])),
            html.Tbody(rows or [html.Tr(html.Td("No events yet", colSpan=5, style={"color": C["muted"]}))]),
        ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "14px", "color": C["text"]},
            className="log")
        log = html.Div(log, style={"overflowX": "auto", "padding": "0 4px 8px"})

        footer = (f"Logging to {store.log_path.name if store.log_path else '—'} · "
                  f"{len(status)} status / {len(events)} event messages kept · "
                  f"{snap['rejected']} ignored (not ours or invalid)")
        return pills, tiles, distance_figure(status, events, since), battery_figure(status, since), log, footer

    return app


def main():
    parser = argparse.ArgumentParser(description="FAHHH? companion dashboard")
    parser.add_argument("--name", default="stanley", help="your name, used in the MQTT client id")
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()

    store = TelemetryStore(log_path=new_log_path())
    start_subscriber(store, client_id=f"fahhh-dash-{args.name}")
    app = build_app(store)
    print(f"Dashboard: http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
