"""FAHHH? companion dashboard (Plotly Dash).

Live view of the device for a companion or station staff:
device online/offline, current state, distance, battery and an event log.
Data comes from MQTT (contracts/C3_mqtt.md); every message is also logged
to dashboard/data/messages_<timestamp>.csv for the test evidence.
Styling lives in assets/style.css (Dash loads it automatically) and follows
Apple's Human Interface Guidelines: system font, grouped lists, system colours.

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

# Apple system colours (fill variants for chart marks; text variants live in style.css)
BLUE, GREEN, ORANGE, RED, GRAY = "#007aff", "#34c759", "#ff9500", "#ff3b30", "#8e8e93"
LABEL, LABEL2, GRID = "#000000", "rgba(60,60,67,0.6)", "#e5e5ea"
STATE_FILL = {"NORMAL": GREEN, "GUIDING": BLUE, "WARNING": ORANGE, "EMERGENCY": RED, "ERROR": GRAY}
FONT = "-apple-system, BlinkMacSystemFont, SF Pro Text, system-ui, Helvetica Neue, Arial, sans-serif"

STATE_LABEL = {"NORMAL": "Normal", "GUIDING": "Guiding", "WARNING": "Warning",
               "EMERGENCY": "Emergency", "ERROR": "Sensor Error"}
EVENTS = {  # event -> (chart marker, title, sentence for the state card)
    "LEVEL_CHANGE": ("triangle-up", "Level Change", "Step or edge ahead"),
    "BOARDING_GAP": ("diamond", "Boarding Gap", "Gap between platform and train"),
    "GUIDE_STEP": ("circle", "Guide Step", "Following the route to the platform"),
    "ARRIVED_PLATFORM": ("star", "Arrived at Platform", "Arrived at the platform"),
    "EMERGENCY": ("square", "Emergency", "Emergency button pressed"),
    "SENSOR_ERROR": ("x", "Sensor Error", "Distance sensor gives no reading"),
    "LOW_BATTERY": ("triangle-down", "Low Battery", "Battery below 20%"),
}


def chart_layout(fig, y_suffix, y_range, height, legend=False):
    fig.update_layout(
        height=height, margin=dict(l=12, r=8, t=12, b=8),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family=FONT, size=12, color=LABEL2),
        hovermode="x unified", uirevision="keep", showlegend=legend,
        legend=dict(orientation="h", x=0, y=-0.18, xanchor="left", yanchor="top",
                    font=dict(size=13, color=LABEL), itemclick=False, itemdoubleclick=False),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=GRID, font=dict(family=FONT, size=13, color=LABEL)),
    )
    fig.update_xaxes(showgrid=False, showline=False, tickformat="%H:%M:%S", nticks=5,
                     showspikes=True, spikemode="across", spikethickness=1, spikecolor=GRAY, spikedash="solid")
    # Health-app style: value labels on the right, light grid
    fig.update_yaxes(side="right", gridcolor=GRID, griddash="dot", zeroline=False, range=y_range,
                     ticksuffix=y_suffix, nticks=5)
    return fig


def waiting(height):
    fig = chart_layout(go.Figure(), "", None, height)
    fig.add_annotation(text="Waiting for data", showarrow=False, font=dict(color=LABEL2, size=15),
                       xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def distance_figure(status, events, since):
    pts = [s for s in status if s["_t"] >= since]
    if not pts:
        return waiting(320)
    fig = chart_layout(go.Figure(), " cm", [0, 320], 320, legend=True)
    fig.add_trace(go.Scatter(
        x=[p["_t"] for p in pts], y=[p["distance_cm"] for p in pts], mode="lines", name="Distance",
        line=dict(color=BLUE, width=2), connectgaps=False, showlegend=False,
        hovertemplate="%{y:.0f} cm<extra>Distance</extra>",
    ))
    for name, (symbol, title, _) in EVENTS.items():
        evs = [e for e in events if e["event"] == name and e["_t"] >= since]
        if evs:
            fig.add_trace(go.Scatter(
                x=[e["_t"] for e in evs],
                y=[e["distance_cm"] if e["distance_cm"] is not None else 0 for e in evs],
                mode="markers", name=title, hovertemplate=f"{title}<extra></extra>",
                marker=dict(symbol=symbol, size=11, line=dict(color="#ffffff", width=2),
                            color=[STATE_FILL.get(e["state"], GRAY) for e in evs]),
            ))
    fig.update_layout(margin=dict(l=12, r=8, t=12, b=56))
    return fig


def battery_figure(status, since):
    pts = [s for s in status if s["_t"] >= since]
    if not pts:
        return waiting(320)
    fig = chart_layout(go.Figure(), "%", [0, 105], 320)
    fig.add_trace(go.Scatter(
        x=[p["_t"] for p in pts], y=[p["battery"] for p in pts], mode="lines",
        line=dict(color=GREEN, width=2), fill="tozeroy", fillcolor="rgba(52,199,89,0.12)",
        hovertemplate="%{y}%<extra>Battery</extra>",
    ))
    fig.add_hline(y=20, line=dict(color=RED, width=1, dash="dash"),
                  annotation_text="Low", annotation_font=dict(color=RED, size=12), annotation_position="top left")
    return fig


def section(header, body, footer=None):
    return html.Div([
        html.Div(header, className="section-header"),
        body,
        html.Div(footer, className="section-footer") if footer is not None else None,
    ], className="section")


def row(label, value, cls="value"):
    return html.Div([html.Span(label), html.Span(value, className=f"{cls} num")], className="row")


def uptime_text(seconds):
    if seconds < 60:
        return f"{seconds} s"
    if seconds < 3600:
        return f"{seconds // 60} min"
    return f"{seconds // 3600} h {seconds % 3600 // 60} min"


def build_app(store):
    app = Dash(__name__, title="FAHHH? unit-01")
    app.layout = html.Div([
        html.Div([
            html.H1("unit-01"),
            html.P("FAHHH? companion view for a blind or low-vision passenger"),
            html.Div(id="status", className="status"),
        ], className="title"),
        html.Div([
            section("Now", html.Div([html.Div(id="state", className="state")], className="group")),
            section("Readings", html.Div(id="readings", className="group")),
        ], className="grid"),
        html.Div([
            section(f"Distance Ahead, Last {WINDOW_MIN} Minutes",
                    html.Div(dcc.Graph(id="distance", config={"displayModeBar": False}), className="group chart"),
                    "Markers show events. Their colour is the state at that moment."),
            section(f"Battery, Last {WINDOW_MIN} Minutes",
                    html.Div(dcc.Graph(id="battery", config={"displayModeBar": False}), className="group chart")),
        ], className="grid wide"),
        section("Events", html.Div(id="log", className="group"), html.Span(id="foot")),
        dcc.Interval(id="tick", interval=REFRESH_MS),
    ], className="page")

    @app.callback(
        Output("status", "children"), Output("state", "children"), Output("readings", "children"),
        Output("distance", "figure"), Output("battery", "figure"), Output("log", "children"),
        Output("foot", "children"),
        Input("tick", "n_intervals"),
    )
    def refresh(_):
        snap = store.snapshot()
        status, events = snap["status"], snap["events"]
        since = datetime.now() - timedelta(minutes=WINDOW_MIN)
        last = status[-1] if status else None

        # Device counts as online only if it said so AND status is fresh
        live = bool(snap["online"]) and not snap["stale"]
        if live:
            device = html.Span([html.B("Online", className="ok"), " device"])
        elif snap["online"] is False:
            device = html.Span([html.B("Offline", className="bad"), " device"])
        else:
            device = html.Span([html.B("No data", className="unknown"), " from device"])
        broker = html.Span([html.B("Connected", className="ok"), " to broker"] if snap["broker_connected"]
                           else [html.B("Disconnected", className="bad"), " from broker"])
        age = snap["status_age_s"]
        updated = html.Span("Updated " + (f"{age:.0f} s ago" if age is not None else "never"), className="num")

        # State card
        if not live:
            key = "NODATA"
            word = "Offline" if snap["online"] is False else "No Data"
            what = "The device is not sending. Alerts still work on the device itself."
        else:
            key = last["state"]
            word = STATE_LABEL.get(key, key.title())
            recent_event = next((e for e in reversed(events) if e["state"] == key), None)
            if key == "NORMAL":
                what = "Path clear"
            elif recent_event:
                what = EVENTS.get(recent_event["event"], (None, None, recent_event["event"]))[2]
            else:
                what = ""
            if key not in ("NORMAL", "ERROR") and last["distance_cm"] is not None:
                what += f", {last['distance_cm']:.0f} cm"
        state = [html.Div(word, className=f"word {key}"), html.Div(what, className="what"),
                 html.Div("Last known readings shown below." if last and not live else "", className="when")]

        # Readings list
        if last:
            recent = [e for e in events if e["_t"] >= since]
            emerg = sum(e["event"] == "EMERGENCY" for e in recent)
            readings = [
                row("Distance Ahead", "No reading" if last["distance_cm"] is None else f"{last['distance_cm']:.0f} cm"),
                row("Battery", f"{last['battery']}%", "value bad" if last["battery"] < 20 else "value"),
                row(f"Events in Last {WINDOW_MIN} Min", f"{len(recent)}"),
                row("Emergencies", f"{emerg}", "value bad" if emerg else "value"),
                row("Device Uptime", uptime_text(last["uptime_s"])),
            ]
        else:
            readings = [row("Distance Ahead", "No data"), row("Battery", "No data"),
                        row(f"Events in Last {WINDOW_MIN} Min", "0")]

        # Event list (newest first)
        rows = []
        for e in reversed(events[-12:]):
            title = EVENTS.get(e["event"], (None, e["event"]))[1]
            dist = "no distance reading" if e["distance_cm"] is None else f"{e['distance_cm']:.0f} cm"
            rows.append(html.Div([
                html.Div([
                    html.Span(title),
                    html.Span([html.Span(STATE_LABEL.get(e["state"], e["state"]), className=e["state"]),
                               f", {dist}, battery {e['battery']}%"], className="sub"),
                ], className="left"),
                html.Span(e["_t"].strftime("%H:%M:%S"), className="time num"),
            ], className="row event"))
        log = rows or [html.Div(html.Span("No events yet", className="empty"), className="row")]

        foot = (f"Every message is saved to data/{store.log_path.name if store.log_path else 'none'}. "
                f"Ignored {snap['rejected']} message(s) that were not from unit-01 or not valid.")
        return ([device, broker, updated], state, readings, distance_figure(status, events, since),
                battery_figure(status, since), log, foot)

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
