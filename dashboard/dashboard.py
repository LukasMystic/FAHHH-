"""FAHHH? companion dashboard (Plotly Dash).

Live view of the cane for a companion or station staff: online/offline,
what the passenger is doing now, where they are on their journey, distance
to the ground, cane tilt and an event log.
Data comes from MQTT (contracts/C3_mqtt.md, v3); every message is also logged
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
TILT_ADVISORY_DEG = 65  # same threshold as the sketch

# Apple system colours (fill variants for chart marks; text variants live in style.css)
BLUE, GREEN, ORANGE, RED, GRAY = "#007aff", "#34c759", "#ff9500", "#ff3b30", "#8e8e93"
LABEL, LABEL2, GRID = "#000000", "rgba(60,60,67,0.6)", "#e5e5ea"
FONT = "-apple-system, BlinkMacSystemFont, SF Pro Text, system-ui, Helvetica Neue, Arial, sans-serif"

# Demo stations (C3 v3, same list as the sketch)
STATIONS = {
    "A01": "Jakarta Kota", "A02": "Jayakarta", "A03": "Mangga Besar", "A04": "Sawah Besar",
    "A05": "Juanda", "A06": "Gondangdia",
    "B01": "Tanah Abang", "B02": "Palmerah", "B03": "Kebayoran", "B04": "Pondok Ranji",
}

# Route states (C3 v3): label and what it means for the companion
STATES = {
    "SELECT_LINE": ("Choosing Line", "The passenger is choosing a line."),
    "SELECT_DEST": ("Choosing Destination", "The passenger is choosing where to go."),
    "SEEK_PLATFORM": ("Finding Platform", "Walking to the platform, waiting for a station tag."),
    "WAIT_TRAIN": ("Waiting for Train", "At the platform."),
    "ON_TRAIN": ("On the Train", "Riding to the destination."),
    "ARRIVING": ("Arriving", "The destination is next. Getting ready to step off."),
    "COMPLETE": ("Arrived", "Journey finished."),
    "EMERGENCY": ("Emergency", "Help requested."),
}
JOURNEY = [  # (step label, states that count as this step)
    ("Choose destination", {"SELECT_LINE", "SELECT_DEST"}),
    ("Find the platform", {"SEEK_PLATFORM"}),
    ("Wait for the train", {"WAIT_TRAIN"}),
    ("Ride the train", {"ON_TRAIN"}),
    ("Arrive", {"ARRIVING"}),
    ("Step off", {"COMPLETE"}),
]

# Events (C3 v3): title and severity class (colour comes from style.css)
EVENTS = {
    "EDGE_WARNING": ("Edge Ahead", "WARNING"),
    "EDGE_CLEAR": ("Edge Cleared", "NORMAL"),
    "CANE_TILT_ADVISORY": ("Cane Tilted Too Far", "WARNING"),
    "HELP_REQUEST": ("Help Requested", "EMERGENCY"),
    "CHECKPOINT": ("Station Tag Read", "INFO"),
    "SIM_TRAIN_NEAR": ("Train at the Door", "INFO"),
    "BOARDING_CONFIRMED_BY_USER": ("Boarded", "INFO"),
    "SIM_DESTINATION_APPROACH": ("Destination Next", "INFO"),
    "ALIGHTING_CONFIRMED_BY_USER": ("Stepped Off", "NORMAL"),
}
SEVERITY_WORD = {"WARNING": "Warning", "EMERGENCY": "Emergency", "NORMAL": "OK", "INFO": "Info"}
CHART_MARKS = {  # event -> (symbol, colour, legend label) on the distance chart
    "EDGE_WARNING": ("triangle-down", ORANGE, "Edge ahead"),
    "CHECKPOINT": ("circle", BLUE, "Station tag"),
    "HELP_REQUEST": ("square", RED, "Help requested"),
}


def station_text(code):
    if not code:
        return "None yet"
    return f"{code} {STATIONS[code]}" if code in STATIONS else code


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
    fig = chart_layout(go.Figure(), " cm", [0, 200], 320, legend=True)
    fig.add_trace(go.Scatter(
        x=[p["_t"] for p in pts], y=[p["distance_cm"] for p in pts], mode="lines", name="Distance",
        line=dict(color=BLUE, width=2), connectgaps=False, showlegend=False,
        hovertemplate="%{y:.0f} cm<extra>Distance to ground</extra>",
    ))
    for name, (symbol, colour, label) in CHART_MARKS.items():
        evs = [e for e in events if e["event"] == name and e["_t"] >= since]
        if evs:
            fig.add_trace(go.Scatter(
                x=[e["_t"] for e in evs],
                y=[e["distance_cm"] if e["distance_cm"] is not None else 0 for e in evs],
                mode="markers", name=label, hovertemplate=f"{label}<extra></extra>",
                marker=dict(symbol=symbol, size=11, color=colour, line=dict(color="#ffffff", width=2)),
            ))
    fig.update_layout(margin=dict(l=12, r=8, t=12, b=56))
    return fig


def tilt_figure(status, since):
    pts = [s for s in status if s["_t"] >= since]
    if not pts:
        return waiting(320)
    fig = chart_layout(go.Figure(), "°", [0, 90], 320)
    fig.add_trace(go.Scatter(
        x=[p["_t"] for p in pts], y=[p["tilt_deg"] for p in pts], mode="lines", connectgaps=False,
        line=dict(color=BLUE, width=2), hovertemplate="%{y:.0f}°<extra>Cane tilt</extra>",
    ))
    fig.add_hline(y=TILT_ADVISORY_DEG, line=dict(color=ORANGE, width=1, dash="dash"),
                  annotation_text="Too far", annotation_font=dict(color=ORANGE, size=12),
                  annotation_position="top left")
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


def now_card(snap, last, live):
    """Big word + sentence. Safety first: help, then edge, then the route state."""
    if not live:
        word, cls = ("Offline" if snap["online"] is False else "No Data"), "NODATA"
        what = "The cane is not sending. Its alerts still work on the cane itself."
        when = "Last known values are shown below." if last else ""
    elif last["help"] or last["state"] == "EMERGENCY":
        word, cls = "Emergency", "EMERGENCY"
        what = "The passenger asked for help. Go to them now."
        when = f"Heading to {station_text(last['dest'])}." if last["dest"] else ""
    elif last["edge"]:
        word, cls = "Edge Ahead", "WARNING"
        dist = f", {last['distance_cm']:.0f} cm to the ground" if last["distance_cm"] is not None else ""
        what = f"Drop-off or step in front of the cane{dist}."
        when = STATES.get(last["state"], (last["state"],))[0]
    else:
        word, what = STATES.get(last["state"], (last["state"].replace("_", " ").title(), ""))
        cls = "NORMAL" if last["state"] == "COMPLETE" else "GUIDING"
        if last["state"] == "WAIT_TRAIN" and last["train_near"]:
            what = "The train is at the door. Waiting for the passenger to confirm boarding."
        if last["state"] in ("ON_TRAIN", "ARRIVING", "COMPLETE") and last["dest"]:
            what += f" Destination {station_text(last['dest'])}."
        when = ""
    return [html.Div(word, className=f"word {cls}"), html.Div(what, className="what"),
            html.Div(when, className="when")]


def journey_rows(last, live):
    if not last:
        return [html.Div(html.Span("Waiting for data", className="empty"), className="row")]
    state = last["state"]
    current = next((i for i, (_, states) in enumerate(JOURNEY) if state in states), None)
    rows = []
    for i, (label, _) in enumerate(JOURNEY):
        if state == "EMERGENCY" or current is None:
            value, cls = "", "value"
        elif i < current or (state == "COMPLETE" and i == current):
            value, cls = "Done", "value NORMAL"
        elif i == current:
            value, cls = "Now" if live else "Last seen", "value GUIDING"
        else:
            value, cls = "", "value"
        rows.append(row(label, value, cls))
    return rows


def build_app(store):
    app = Dash(__name__, title="FAHHH? unit-01")
    app.layout = html.Div([
        html.Div([
            html.H1("unit-01"),
            html.P("FAHHH? companion view for a blind or low-vision passenger"),
            html.Div(id="status", className="status"),
        ], className="title"),
        html.Div([
            html.Div([
                section("Now", html.Div([html.Div(id="state", className="state")], className="group")),
                section("Readings", html.Div(id="readings", className="group")),
            ]),
            section("Journey", html.Div(id="journey", className="group")),
        ], className="grid"),
        html.Div([
            section(f"Distance to Ground, Last {WINDOW_MIN} Minutes",
                    html.Div(dcc.Graph(id="distance", config={"displayModeBar": False}), className="group chart"),
                    "A sudden rise means the ground drops away: an edge or a step down."),
            section(f"Cane Tilt, Last {WINDOW_MIN} Minutes",
                    html.Div(dcc.Graph(id="tilt", config={"displayModeBar": False}), className="group chart"),
                    "Above 65° the edge reading is not reliable."),
        ], className="grid wide"),
        section("Events", html.Div(id="log", className="group"), html.Span(id="foot")),
        dcc.Interval(id="tick", interval=REFRESH_MS),
    ], className="page")

    @app.callback(
        Output("status", "children"), Output("state", "children"), Output("readings", "children"),
        Output("journey", "children"), Output("distance", "figure"), Output("tilt", "figure"),
        Output("log", "children"), Output("foot", "children"),
        Input("tick", "n_intervals"),
    )
    def refresh(_):
        snap = store.snapshot()
        status, events = snap["status"], snap["events"]
        since = datetime.now() - timedelta(minutes=WINDOW_MIN)
        last = status[-1] if status else None

        # The cane counts as online only if it said so AND status is fresh
        live = bool(snap["online"]) and not snap["stale"]
        if live:
            device = html.Span([html.B("Online", className="ok"), " cane"])
        elif snap["online"] is False:
            device = html.Span([html.B("Offline", className="bad"), " cane"])
        else:
            device = html.Span([html.B("No data", className="unknown"), " from cane"])
        broker = html.Span([html.B("Connected", className="ok"), " to broker"] if snap["broker_connected"]
                           else [html.B("Disconnected", className="bad"), " from broker"])
        age = snap["status_age_s"]
        updated = html.Span("Updated " + (f"{age:.0f} s ago" if age is not None else "never"), className="num")

        if last:
            recent = [e for e in events if e["_t"] >= since]
            helps = sum(e["event"] == "HELP_REQUEST" for e in recent)
            edges = sum(e["event"] == "EDGE_WARNING" for e in recent)
            readings = [
                row("Destination", station_text(last["dest"]) if last["dest"] else "Not chosen yet"),
                row("Last Station Tag", station_text(last["station"])),
                row("Distance to Ground", "No reading" if last["distance_cm"] is None else f"{last['distance_cm']:.0f} cm",
                    "value WARNING" if last["edge"] else "value"),
                row("Cane Tilt", "No reading" if last["tilt_deg"] is None else f"{last['tilt_deg']:.0f}°",
                    "value WARNING" if (last["tilt_deg"] or 0) > TILT_ADVISORY_DEG else "value"),
                row("Train at Door", "Yes" if last["train_near"] else "No"),
                row(f"Edge Warnings, Last {WINDOW_MIN} Min", f"{edges}", "value WARNING" if edges else "value"),
                row(f"Help Requests, Last {WINDOW_MIN} Min", f"{helps}", "value EMERGENCY" if helps else "value"),
                row("Cane Uptime", uptime_text(last["uptime_s"])),
            ]
        else:
            readings = [row("Destination", "No data"), row("Distance to Ground", "No data")]

        rows = []
        for e in reversed(events[-12:]):
            if e["event"] in EVENTS:
                title, sev = EVENTS[e["event"]]
                sev_word = SEVERITY_WORD[sev]
            elif e["event"] in STATES:  # state change events carry the state's name
                title, sev, sev_word = f"Now: {STATES[e['event']][0]}", "INFO", "Info"
            else:
                title, sev, sev_word = e["event"].replace("_", " ").title(), "INFO", "Info"
            detail = []
            if e["distance_cm"] is not None and e["event"] in ("EDGE_WARNING", "EDGE_CLEAR", "HELP_REQUEST"):
                detail.append(f"{e['distance_cm']:.0f} cm")
            if e["source"]:
                detail.append(f"from {e['source'].replace('_', ' ').lower()}")
            rows.append(html.Div([
                html.Div([
                    html.Span(title),
                    html.Span([html.Span(sev_word, className=sev)] + [f", {d}" for d in detail], className="sub"),
                ], className="left"),
                html.Span(e["_t"].strftime("%H:%M:%S"), className="time num"),
            ], className="row event"))
        log = rows or [html.Div(html.Span("No events yet", className="empty"), className="row")]

        foot = (f"Every message is saved to data/{store.log_path.name if store.log_path else 'none'}. "
                f"Ignored {snap['rejected']} message(s) that were not from unit-01 or not valid.")
        return ([device, broker, updated], now_card(snap, last, live), readings, journey_rows(last, live),
                distance_figure(status, events, since), tilt_figure(status, since), log, foot)

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
