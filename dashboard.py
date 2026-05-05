from __future__ import annotations

from collections import Counter
from datetime import datetime

from flask import Response

from utils.storage import (
    get_all_potholes,
    get_counts,
    get_hourly_counts,
    get_severity_counts,
    get_status_counts,
    get_zone_counts,
)


# ── Data helpers — mirror the API logic but call storage directly ────
# Flask dev-server is single-threaded so HTTP self-calls deadlock.
# These functions replicate what /api/potholes, /api/stats and
# /api/hotspots return, but without going through the network.


def _data_potholes(limit: int = 100) -> list:
    """Same result as GET /api/potholes → potholes list."""
    try:
        return get_all_potholes(limit=limit)
    except Exception as exc:
        print(f"[DASHBOARD][ERROR] potholes query failed: {exc}")
        return []


def _data_stats() -> dict:
    """Same result as GET /api/stats."""
    try:
        counts = get_counts()
        total = counts.get("total", 0)
        fixed = counts.get("fixed", 0)
        fix_rate = round((fixed / total) * 100, 2) if total else 0.0
        return {
            **counts,
            "fix_rate": fix_rate,
            "hourly": get_hourly_counts(hours=8),
            "zones": get_zone_counts(),
            "status_counts": get_status_counts(),
            "severity_counts": get_severity_counts(),
        }
    except Exception as exc:
        print(f"[DASHBOARD][ERROR] stats query failed: {exc}")
        return {}


def _data_hotspots() -> list:
    """Same result as GET /api/hotspots."""
    try:
        zones = get_zone_counts()
        return [z for z in zones if z.get("count", 0) > 1]
    except Exception as exc:
        print(f"[DASHBOARD][ERROR] hotspots query failed: {exc}")
        return []


# ── Dash imports (graceful fallback) ─────────────────────────────────
try:
    import dash
    import plotly.graph_objects as go
    from dash import Input, Output, State, callback_context, dash_table, dcc, html
except ImportError:  # pragma: no cover
    dash = None
    go = None
    Input = Output = State = callback_context = dash_table = dcc = html = None


# ══════════════════════════════════════════════════════════════════════
# Digital India / Government of India — Colour Palette
# Saffron (#FF9933) · White (#FFFFFF) · Green (#138808) · Navy (#000080)
# ══════════════════════════════════════════════════════════════════════
COLORS = {
    # GoI core palette
    "saffron":       "#FF9933",
    "white":         "#FFFFFF",
    "india_green":   "#138808",
    "navy":          "#000080",
    # UI surfaces
    "bg":            "#F4F6F9",       # light off-white gov background
    "panel":         "#FFFFFF",       # white card panels
    "panel_border":  "#D1D5DB",       # subtle grey border
    "header_bg":     "#1B2A4A",       # deep navy header
    "header_text":   "#FFFFFF",
    # Semantic
    "red":           "#DC2626",
    "amber":         "#D97706",
    "green":         "#16A34A",
    "blue":          "#2563EB",
    # Text
    "text_dark":     "#1E293B",
    "text":          "#374151",
    "text_light":    "#6B7280",
    "text_muted":    "#9CA3AF",
    # Accents
    "saffron_light": "#FFF3E0",
    "green_light":   "#E8F5E9",
    "blue_light":    "#E3F2FD",
    "red_light":     "#FFEBEE",
}

# ── Font stack (official feel) ───────────────────────────────────────
FONT_STACK = "'Noto Sans', 'Segoe UI', 'Roboto', Arial, sans-serif"
FONT_MONO  = "'Roboto Mono', 'Consolas', monospace"


# ── Mount entrypoint ─────────────────────────────────────────────────


def mount_dashboard(server):
    """Mount the Plotly Dash dashboard on the shared Flask server."""
    if dash is None:

        @server.get("/dashboard/")
        def dashboard_unavailable() -> Response:
            return Response(
                "<h1>RoadWatch AI Dashboard</h1>"
                "<p>Dash is not installed in this environment.</p>",
                mimetype="text/html",
            )

        print("[DASH][WARN] Dash not installed. Fallback route registered.")
        return None

    app = dash.Dash(
        __name__,
        server=server,
        routes_pathname_prefix="/dashboard/",
        suppress_callback_exceptions=True,
    )
    app.title = "RoadWatch AI — National Road Infrastructure Monitoring Portal"

    # Inject Google Fonts + custom CSS via index_string
    app.index_string = """
    <!DOCTYPE html>
    <html lang="en">
        <head>
            {%metas%}
            <title>{%title%}</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700;800&family=Roboto+Mono:wght@400;500;600&display=swap" rel="stylesheet">
            {%favicon%}
            {%css%}
            <style>
                *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
                html { scroll-behavior: smooth; }
                body {
                    font-family: 'Noto Sans', 'Segoe UI', 'Roboto', Arial, sans-serif;
                    background: #F4F6F9;
                    color: #374151;
                    -webkit-font-smoothing: antialiased;
                }
                ::-webkit-scrollbar { width: 7px; }
                ::-webkit-scrollbar-track { background: #E5E7EB; }
                ::-webkit-scrollbar-thumb { background: #9CA3AF; border-radius: 4px; }
                ::-webkit-scrollbar-thumb:hover { background: #6B7280; }

                /* ── Tri-colour banner ── */
                .goi-tricolour {
                    position: fixed; top: 0; left: 0; right: 0; height: 5px; z-index: 9999;
                    background: linear-gradient(90deg,
                        #FF9933 0%, #FF9933 33.33%,
                        #FFFFFF 33.33%, #FFFFFF 66.66%,
                        #138808 66.66%, #138808 100%);
                }

                /* ── STAT CARD — hover lift ── */
                .stat-card {
                    transition: transform 0.25s ease, box-shadow 0.25s ease;
                }
                .stat-card:hover {
                    transform: translateY(-4px);
                    box-shadow: 0 8px 24px rgba(0,0,0,0.10), 0 2px 6px rgba(0,0,0,0.06) !important;
                }

                /* ── CHART PANEL — fade-in on load ── */
                @keyframes fadeSlideUp {
                    from { opacity: 0; transform: translateY(18px); }
                    to   { opacity: 1; transform: translateY(0); }
                }
                .chart-panel {
                    animation: fadeSlideUp 0.5s ease-out both;
                }
                .chart-panel:nth-child(1) { animation-delay: 0.05s; }
                .chart-panel:nth-child(2) { animation-delay: 0.15s; }
                .chart-panel:nth-child(3) { animation-delay: 0.25s; }

                /* ── PROGRESS BAR — animated grow ── */
                @keyframes growWidth {
                    from { width: 0 !important; }
                }
                .progress-fill {
                    animation: growWidth 0.8s ease-out both;
                }

                /* ── TABLE ROW — hover & active effects ── */
                .dash-spreadsheet-container .dash-spreadsheet-inner td,
                .dash-spreadsheet-container .dash-spreadsheet-inner th {
                    font-family: 'Roboto Mono', 'Consolas', monospace !important;
                    font-size: 12px !important;
                    transition: background-color 0.15s ease, transform 0.1s ease;
                }
                .dash-spreadsheet-container .dash-spreadsheet-inner tr:hover td {
                    background-color: #EEF2FF !important;
                    cursor: pointer;
                }
                .dash-spreadsheet-container .dash-spreadsheet-inner tr:active td {
                    background-color: #E0E7FF !important;
                    transform: scale(0.995);
                }
                .dash-spreadsheet-container .dash-spreadsheet-inner tr {
                    transition: all 0.15s ease;
                }
                .dash-spreadsheet-container .dash-spreadsheet-inner tr:hover {
                    box-shadow: inset 3px 0 0 #FF9933;
                }

                /* ── FILTER BUTTONS ── */
                .btn-filter {
                    background-color: transparent;
                    border-radius: 6px;
                    padding: 7px 16px;
                    font-weight: 600;
                    font-size: 12px;
                    cursor: pointer;
                    letter-spacing: 0.5px;
                    transition: all 0.2s ease;
                    font-family: inherit;
                }
                .btn-filter-blue { border: 2px solid #2563EB; color: #2563EB; }
                .btn-filter-blue:hover, .btn-filter-blue:active { background-color: #2563EB; color: #fff; }
                
                .btn-filter-red { border: 2px solid #DC2626; color: #DC2626; }
                .btn-filter-red:hover, .btn-filter-red:active { background-color: #DC2626; color: #fff; }

                .btn-filter-amber { border: 2px solid #D97706; color: #D97706; }
                .btn-filter-amber:hover, .btn-filter-amber:active { background-color: #D97706; color: #fff; }

                .btn-filter-green { border: 2px solid #16A34A; color: #16A34A; }
                .btn-filter-green:hover, .btn-filter-green:active { background-color: #16A34A; color: #fff; }

                /* ── RESPONSIVE DESIGN ── */
                @media (max-width: 768px) {
                    .nav-header { flex-direction: column; align-items: flex-start !important; gap: 12px; padding: 14px 16px !important; }
                    .header-right { align-items: flex-start !important; margin-top: 10px; width: 100%; }
                    .live-clock-div { text-align: left !important; }
                    .content-wrapper { padding: 16px !important; }
                    .stat-cards-grid, .charts-grid, .charts-grid-2 { display: flex !important; flex-direction: column !important; }
                    .filter-row { flex-wrap: wrap; }
                    .btn-filter { flex: 1 1 45%; text-align: center; font-size: 11px; }
                    .footer-txt { flex-direction: column; gap: 8px; text-align: center; }
                }
            </style>
        </head>
        <body>
            <div class="goi-tricolour"></div>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
            <script>
            /* ── Counter animation for stat cards (once on load) ── */
            (function() {
                var animated = {};

                function animateCounter(el) {
                    if (animated[el.id]) return;
                    var raw = el.textContent.trim();
                    var isPercent = raw.endsWith('%');
                    var numStr = raw.replace(/[^0-9.]/g, '');
                    var target = parseFloat(numStr);
                    if (isNaN(target) || target === 0) return;
                    
                    animated[el.id] = true;
                    var duration = 1200;
                    var startTime = performance.now();
                    var isInt = target === Math.floor(target) && !isPercent;
                    
                    function fmt(n) {
                        var s = isInt ? Math.round(n).toLocaleString() : n.toFixed(2);
                        return isPercent ? s + '%' : s;
                    }
                    
                    function step(now) {
                        var t = Math.min((now - startTime) / duration, 1);
                        var ease = 1 - Math.pow(1 - t, 3);
                        el.textContent = fmt(target * ease);
                        if (t < 1) {
                            requestAnimationFrame(step);
                        } else {
                            el.textContent = raw; // Restore Dash's original exact string
                        }
                    }
                    requestAnimationFrame(step);
                }

                var cardIds = ['card-total','card-pending','card-progress','card-fixed','card-high','card-rate'];
                var obs = new MutationObserver(function(mutations) {
                    mutations.forEach(function(m) {
                        var el = m.target.nodeType === 1 ? m.target : m.target.parentElement;
                        if (el && cardIds.indexOf(el.id) !== -1) {
                            animateCounter(el);
                        }
                    });
                });

                window.addEventListener('DOMContentLoaded', function() {
                    obs.observe(document.body, {childList: true, characterData: true, subtree: true});
                });
            })();
            </script>
        </body>
    </html>
    """

    app.layout = _build_layout()
    _register_callbacks(app)
    return app


# ── Reusable style helpers ───────────────────────────────────────────


def _panel_style(**overrides) -> dict:
    """White card panel with subtle shadow — clean gov style."""
    base = {
        "backgroundColor": COLORS["panel"],
        "border": f"1px solid {COLORS['panel_border']}",
        "borderRadius": "8px",
        "padding": "20px",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)",
    }
    base.update(overrides)
    return base


def _card(title: str, value_id: str, accent: str, icon_char: str = "●"):
    """GoI-style stat card with saffron/green/navy accent stripe."""
    return html.Div(
        [
            # Accent top stripe
            html.Div(style={
                "height": "4px",
                "backgroundColor": accent,
                "borderRadius": "8px 8px 0 0",
                "margin": "-20px -20px 14px -20px",
            }),
            # Icon + label
            html.Div(
                [
                    html.Span(icon_char, style={
                        "fontSize": "16px", "color": accent, "marginRight": "8px",
                    }),
                    html.Span(title.upper(), style={
                        "fontSize": "11px", "fontWeight": "600",
                        "color": COLORS["text_light"],
                        "letterSpacing": "0.8px",
                    }),
                ],
                style={"display": "flex", "alignItems": "center", "marginBottom": "8px"},
            ),
            # Value
            html.Div(
                id=value_id,
                style={
                    "fontSize": "28px", "fontWeight": "800",
                    "color": COLORS["text_dark"],
                    "fontFamily": FONT_MONO,
                    "lineHeight": "1.2",
                },
            ),
        ],
        style=_panel_style(),
        className="stat-card",
    )


def _section_header(title: str, subtitle: str = "", accent: str = None):
    """Section divider with coloured left bar — like gov portal sections."""
    c = accent or COLORS["saffron"]
    return html.Div(
        [
            html.Div(style={
                "width": "4px", "minHeight": "24px",
                "backgroundColor": c, "borderRadius": "2px", "marginRight": "12px",
            }),
            html.Div([
                html.Span(title, style={
                    "fontSize": "15px", "fontWeight": "700",
                    "color": COLORS["text_dark"], "letterSpacing": "0.5px",
                }),
                html.Span(
                    f"  —  {subtitle}" if subtitle else "",
                    style={"fontSize": "12px", "color": COLORS["text_light"]},
                ),
            ]),
        ],
        style={"display": "flex", "alignItems": "center", "marginBottom": "14px"},
    )


def _chart_layout(title: str) -> dict:
    return {
        "title": {
            "text": title,
            "font": {"color": COLORS["text_dark"], "size": 14, "family": FONT_STACK},
            "x": 0.02, "xanchor": "left",
        },
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"color": COLORS["text"], "family": FONT_MONO, "size": 11},
        "margin": {"l": 40, "r": 20, "t": 50, "b": 30},
        "xaxis": {"gridcolor": "#E5E7EB", "zerolinecolor": "#E5E7EB"},
        "yaxis": {"gridcolor": "#E5E7EB", "zerolinecolor": "#E5E7EB"},
    }


# ── Layout ───────────────────────────────────────────────────────────


def _build_layout():
    return html.Div(
        [
            # Auto-refresh every 3 s
            dcc.Interval(id="refresh", interval=3000, n_intervals=0),
            dcc.Store(id="status-filter", data="All"),

            # ══════════════════════════════════════════════════════
            # HEADER — Official Government Portal Banner
            # ══════════════════════════════════════════════════════
            html.Div(
                [
                    # Left: Emblem + Title
                    html.Div(
                        [
                            # Ashoka Chakra inspired emblem
                            html.Div("☸", style={
                                "fontSize": "36px", "color": COLORS["saffron"],
                                "marginRight": "14px", "lineHeight": "1",
                            }),
                            html.Div([
                                html.Div(
                                    [
                                        html.Span("ROADWATCH ", style={
                                            "fontWeight": "800", "color": COLORS["white"],
                                        }),
                                        html.Span("AI", style={
                                            "fontWeight": "800", "color": COLORS["saffron"],
                                        }),
                                    ],
                                    style={"fontSize": "24px", "letterSpacing": "1.5px"},
                                ),
                                html.Div(
                                    "National Road Infrastructure Monitoring Portal",
                                    style={
                                        "fontSize": "11px", "fontWeight": "500",
                                        "color": "#94A3B8", "letterSpacing": "1px",
                                        "marginTop": "2px",
                                    },
                                ),
                            ]),
                        ],
                        style={"display": "flex", "alignItems": "center"},
                    ),

                
                    # Right: Clock + Live button
                    html.Div(
                        [
                            html.Div(
                                id="live-clock",
                                className="live-clock-div",
                                style={
                                    "fontSize": "15px", "fontWeight": "600",
                                    "fontFamily": FONT_MONO,
                                    "color": COLORS["white"], "textAlign": "right",
                                },
                            ),
                            html.A(
                                html.Button("◉ LIVE MONITORING", style={
                                    "padding": "6px 16px",
                                    "backgroundColor": COLORS["india_green"],
                                    "color": "#fff", "borderRadius": "4px",
                                    "fontWeight": "700", "border": "none",
                                    "cursor": "pointer", "fontSize": "11px",
                                    "letterSpacing": "1px",
                                }),
                                href="/camera/start", target="_blank",
                                style={"marginTop": "6px", "display": "inline-block",
                                       "textDecoration": "none"},
                            ),
                        ],
                        className="header-right",
                        style={"display": "flex", "flexDirection": "column",
                               "alignItems": "flex-end"},
                    ),
                ],
                className="nav-header",
                style={
                    "display": "flex", "justifyContent": "space-between",
                    "alignItems": "center",
                    "padding": "14px 32px",
                    "backgroundColor": COLORS["header_bg"],
                    "borderBottom": f"3px solid {COLORS['saffron']}",
                    "marginTop": "5px",  # below tri-colour strip
                },
            ),

            # ══════════════════════════════════════════════════════
            # CONTENT
            # ══════════════════════════════════════════════════════
            html.Div(
                [
                    # ── Stat cards ─────────────────────────────────
                    _section_header("System Metrics", "Real-time infrastructure status", COLORS["navy"]),
                    html.Div(
                        [
                            _card("Potholes Detected", "card-total", COLORS["navy"], "⬡"),
                            _card("Pending Repair", "card-pending", COLORS["red"], "⚠"),
                            _card("In Progress", "card-progress", COLORS["amber"], "⟳"),
                            _card("Fixed", "card-fixed", COLORS["india_green"], "✓"),
                            _card("High Severity", "card-high", COLORS["saffron"], "▲"),
                            _card("Fix Rate %", "card-rate", COLORS["green"], "◎"),
                        ],
                        className="stat-cards-grid",
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fit, minmax(150px, 1fr))",
                            "gap": "16px", "marginBottom": "28px",
                        },
                    ),

                    # ── Charts Row 1 ──────────────────────────────
                    _section_header("Analytics", "Detection telemetry & classification", COLORS["saffron"]),
                    html.Div(
                        [
                            html.Div(
                                dcc.Graph(id="hourly-chart", config={"displayModeBar": False},
                                          animate=True, animation_options={"frame": {"redraw": True}}),
                                style=_panel_style(), className="chart-panel",
                            ),
                            html.Div(
                                dcc.Graph(id="status-chart", config={"displayModeBar": False},
                                          animate=True, animation_options={"frame": {"redraw": True}}),
                                style=_panel_style(), className="chart-panel",
                            ),
                            html.Div(
                                dcc.Graph(id="severity-chart", config={"displayModeBar": False},
                                          animate=True, animation_options={"frame": {"redraw": True}}),
                                style=_panel_style(), className="chart-panel",
                            ),
                        ],
                        className="charts-grid",
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))",
                            "gap": "16px", "marginBottom": "28px",
                        },
                    ),

                    # ── Charts Row 2 ──────────────────────────────
                    html.Div(
                        [
                            html.Div(
                                dcc.Graph(id="zone-chart", config={"displayModeBar": False},
                                          animate=True, animation_options={"frame": {"redraw": True}}),
                                style=_panel_style(), className="chart-panel",
                            ),
                            html.Div(
                                dcc.Graph(id="funnel-chart", config={"displayModeBar": False},
                                          animate=True, animation_options={"frame": {"redraw": True}}),
                                style=_panel_style(), className="chart-panel",
                            ),
                        ],
                        className="charts-grid-2",
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))",
                            "gap": "16px", "marginBottom": "28px",
                        },
                    ),
                    # ── Live Map ─────────────────────────────
                    _section_header("Live Map", "Real-time pothole locations", COLORS["blue"]),
                    html.Div(
                        html.Iframe(
                            src="/map",
                            style={
                                "width": "100%",
                                "height": "500px",
                                "border": "none",
                                "borderRadius": "8px"
                            }
                        ),
                        style=_panel_style(),
                        ),

                    # ── Zone Progress ─────────────────────────────
                    _section_header("Zone Repair Progress", "District-level remediation", COLORS["india_green"]),
                    html.Div(
                        id="zone-progress",
                        style={**_panel_style(), "marginBottom": "28px"},
                    ),

                    # ── Hotspot Zones ─────────────────────────────
                    _section_header("Hotspot Zones", "Critical infrastructure alerts", COLORS["red"]),
                    html.Div(
                        [html.Div(id="hotspot-list")],
                        style={**_panel_style(), "marginBottom": "28px"},
                    ),

                    # ── Live Incident Table ───────────────────────
                    _section_header("Live Incident Log", "Real-time detection feed", COLORS["navy"]),
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Button("All", id="filter-all", n_clicks=0,
                                                className="btn-filter btn-filter-blue"),
                                    html.Button("Pending", id="filter-pending", n_clicks=0,
                                                className="btn-filter btn-filter-red"),
                                    html.Button("In Progress", id="filter-progress", n_clicks=0,
                                                className="btn-filter btn-filter-amber"),
                                    html.Button("Fixed", id="filter-fixed", n_clicks=0,
                                                className="btn-filter btn-filter-green"),
                                ],
                                className="filter-row",
                                style={"display": "flex", "gap": "10px", "marginBottom": "14px"},
                            ),
                            dash_table.DataTable(
                                id="live-table",
                                style_table={'overflowX': 'auto'},
                                columns=[
                                    {"name": "Type", "id": "hazard_type"},
                                    {"name": "Zone", "id": "zone"},
                                    {"name": "Address", "id": "address"},
                                    {"name": "Rank/Score", "id": "priority_score"},
                                    {"name": "Detections", "id": "detection_count"},
                                    {"name": "Status", "id": "status"},
                                    {"name": "AI Verification", "id": "verification_status"},
                                    {"name": "Maps", "id": "maps_link", "presentation": "markdown"},
                                    {"name": "First Seen", "id": "timestamp"},
                                ],
                                style_as_list_view=True,
                                style_header={
                                    "backgroundColor": COLORS["header_bg"],
                                    "color": COLORS["white"],
                                    "border": "none",
                                    "fontWeight": "600",
                                    "fontSize": "11px",
                                    "letterSpacing": "0.8px",
                                    "padding": "12px 10px",
                                },
                                style_cell={
                                    "backgroundColor": COLORS["panel"],
                                    "color": COLORS["text"],
                                    "border": "none",
                                    "borderBottom": f"1px solid {COLORS['panel_border']}",
                                    "padding": "10px",
                                    "fontFamily": FONT_MONO,
                                    "fontSize": "12px",
                                    "textAlign": "left",
                                    "whiteSpace": "normal",
                                    "height": "auto",
                                },
                                style_data_conditional=[
                                    {
                                        "if": {"filter_query": '{status} = "Pending"', "column_id": "status"},
                                        "color": COLORS["red"],
                                    },
                                    {
                                        "if": {"filter_query": '{status} = "Fixed"', "column_id": "status"},
                                        "color": COLORS["india_green"],
                                    },
                                    {
                                        "if": {"filter_query": '{status} = "In Progress"', "column_id": "status"},
                                        "color": COLORS["amber"],
                                    },
                                    {
                                        "if": {"filter_query": '{verification_status} = "Verified"', "column_id": "verification_status"},
                                        "color": COLORS["india_green"],
                                        "fontWeight": "bold",
                                    },
                                    {
                                        "if": {"filter_query": '{verification_status} = "Auto-Resolved"', "column_id": "verification_status"},
                                        "color": COLORS["blue"],
                                        "fontWeight": "bold",
                                    },
                                    {
                                        "if": {"row_index": "odd"},
                                        "backgroundColor": "#F9FAFB",
                                    },
                                ],
                                page_size=20,
                            ),
                        ],
                        style=_panel_style(),
                    ),

                    # ── Footer ────────────────────────────────────
                    html.Div(
                        [
                            # Tri-colour line
                            html.Div(style={
                                "height": "3px", "marginBottom": "14px",
                                "background": f"linear-gradient(90deg, {COLORS['saffron']}, {COLORS['white']}, {COLORS['india_green']})",
                                "borderRadius": "2px",
                            }),
                            html.Div(
                                [
                                    html.Span(
                                        "© RoadWatch AI  ·  National Road Infrastructure Monitoring Portal  ·  Digital India Initiative",
                                        style={"fontSize": "11px", "color": COLORS["text_muted"]},
                                    ),
                                    html.Span(
                                        "Powered by YOLO v11 · OpenCV · MongoDB · Plotly",
                                        style={"fontSize": "11px", "color": COLORS["text_muted"]},
                                    ),
                                ],
                                className="footer-txt",
                                style={"display": "flex", "justifyContent": "space-between"},
                            ),
                        ],
                        style={"marginTop": "40px", "paddingBottom": "24px"},
                    ),
                ],
                className="content-wrapper",
                style={
                    "padding": "28px 32px",
                    "maxWidth": "1440px",
                    "margin": "0 auto",
                },
            ),
        ],
        style={
            "minHeight": "100vh",
            "backgroundColor": COLORS["bg"],
            "fontFamily": FONT_STACK,
            "color": COLORS["text"],
        },
    )


# ── Callbacks ────────────────────────────────────────────────────────


def _register_callbacks(app) -> None:

    # ── Cards  <-  /api/stats logic ──────────────────────────────────
    @app.callback(
        Output("card-total", "children"),
        Output("card-pending", "children"),
        Output("card-progress", "children"),
        Output("card-fixed", "children"),
        Output("card-high", "children"),
        Output("card-rate", "children"),
        Output("live-clock", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_cards(_):
        s = _data_stats()
        now = datetime.now()
        clock_display = [
            html.Div(now.strftime("%H:%M:%S"), style={
                "fontSize": "16px", "fontWeight": "700", "letterSpacing": "1px",
            }),
            html.Div(now.strftime("%d %b %Y").upper(), style={
                "fontSize": "10px", "color": "#94A3B8", "letterSpacing": "0.8px",
            }),
        ]
        return (
            f'{s.get("total", 0):,}',
            f'{s.get("pending", 0):,}',
            f'{s.get("in_progress", 0):,}',
            f'{s.get("fixed", 0):,}',
            f'{s.get("high_severity", 0):,}',
            f'{s.get("fix_rate", 0)}%',
            clock_display,
        )

    # ── Charts  <-  /api/stats + /api/potholes logic ────────────────
    @app.callback(
        Output("hourly-chart", "figure"),
        Output("status-chart", "figure"),
        Output("severity-chart", "figure"),
        Output("zone-chart", "figure"),
        Output("funnel-chart", "figure"),
        Output("zone-progress", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_charts(_):
        s = _data_stats()
        records = _data_potholes(limit=10000)

        # ── Hourly area chart
        hourly = s.get("hourly", [])
        hourly_fig = go.Figure(
            go.Scatter(
                x=[h["hour"] for h in hourly],
                y=[h["count"] for h in hourly],
                fill="tozeroy",
                fillcolor="rgba(37, 99, 235, 0.08)",
                line={"color": COLORS["blue"], "width": 2, "shape": "spline"},
                mode="lines+markers",
                marker={"size": 6, "color": COLORS["blue"]},
            )
        )
        hourly_fig.update_layout(_chart_layout("Hourly Detections"))
        hourly_fig.update_layout(height=280)

        # ── Status donut
        st = s.get("status_counts", {"Pending": 0, "Fixed": 0, "In Progress": 0})
        status_fig = go.Figure(
            go.Pie(
                labels=list(st.keys()),
                values=list(st.values()),
                hole=0.6,
                marker={
                    "colors": [COLORS["red"], COLORS["india_green"], COLORS["amber"]],
                    "line": {"width": 2, "color": COLORS["panel"]},
                },
                textinfo="label+percent",
                textfont={"size": 11, "family": FONT_STACK},
            )
        )
        status_fig.update_layout(_chart_layout("Repair Status"))
        status_fig.update_layout(height=280, showlegend=False)

        # ── Severity donut
        sv = s.get("severity_counts", {"High": 0, "Medium": 0, "Low": 0})
        severity_fig = go.Figure(
            go.Pie(
                labels=list(sv.keys()),
                values=list(sv.values()),
                hole=0.6,
                marker={
                    "colors": [COLORS["saffron"], COLORS["amber"], COLORS["blue"]],
                    "line": {"width": 2, "color": COLORS["panel"]},
                },
                textinfo="label+percent",
                textfont={"size": 11, "family": FONT_STACK},
            )
        )
        severity_fig.update_layout(_chart_layout("Severity Split"))
        severity_fig.update_layout(height=280, showlegend=False)

        # ── Zone horizontal bar
        zones = s.get("zones", [])
        zone_fig = go.Figure(
            go.Bar(
                x=[z["count"] for z in zones],
                y=[z["zone"] for z in zones],
                orientation="h",
                marker={
                    "color": [z["count"] for z in zones],
                    "colorscale": [[0, COLORS["india_green"]], [1, COLORS["saffron"]]],
                },
            )
        )
        zone_fig.update_layout(_chart_layout("Zones Ranked"))
        zone_fig.update_layout(height=280)

        # ── Repair funnel
        funnel_fig = go.Figure(
            go.Funnel(
                y=["Detected", "In Progress", "Fixed"],
                x=[s.get("total", 0), s.get("in_progress", 0), s.get("fixed", 0)],
                marker={"color": [COLORS["blue"], COLORS["amber"], COLORS["india_green"]]},
                textfont={"family": FONT_MONO, "size": 12},
            )
        )
        funnel_fig.update_layout(_chart_layout("Repair Funnel"))
        funnel_fig.update_layout(height=280)

        # ── Zone progress bars
        progress = []
        for z in zones[:8]:
            name = z["zone"]
            total = z["count"]
            fixed_n = sum(
                1 for r in records
                if r.get("zone") == name and r.get("status") == "Fixed"
            )
            pct = round((fixed_n / total) * 100, 2) if total else 0.0
            progress.append(
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span(name, style={
                                    "fontWeight": "600", "fontSize": "13px",
                                    "color": COLORS["text_dark"],
                                }),
                                html.Span(f"{pct}%", style={
                                    "fontWeight": "700", "fontSize": "13px",
                                    "color": COLORS["india_green"],
                                    "fontFamily": FONT_MONO,
                                }),
                            ],
                            style={"display": "flex", "justifyContent": "space-between",
                                   "marginBottom": "6px"},
                        ),
                        html.Div(
                            html.Div(style={
                                "width": f"{pct}%", "height": "8px",
                                "background": f"linear-gradient(90deg, {COLORS['india_green']}, {COLORS['saffron']})",
                                "borderRadius": "4px",
                                "transition": "width 0.6s ease",
                            }, className="progress-fill"),
                            style={
                                "backgroundColor": "#E5E7EB",
                                "borderRadius": "4px", "overflow": "hidden",
                            },
                        ),
                    ],
                    style={"marginBottom": "14px"},
                )
            )

        return hourly_fig, status_fig, severity_fig, zone_fig, funnel_fig, progress

    # ── Hotspots  <-  /api/hotspots logic ────────────────────────────
    @app.callback(
        Output("hotspot-list", "children"),
        Input("refresh", "n_intervals"),
    )
    def update_hotspots(_):
        hotspots = _data_hotspots()
        if not hotspots:
            return html.Div(
                "No hotspot zones detected.",
                style={"color": COLORS["text_muted"]},
            )

        chips = []
        for spot in hotspots:
            zone = spot.get("zone", "Unknown")
            count = spot.get("count", 0)
            chips.append(
                html.Div(
                    [
                        html.Span("▲ ", style={
                            "color": COLORS["saffron"], "fontSize": "14px", "marginRight": "6px",
                        }),
                        html.Span(zone, style={"fontWeight": "700", "fontSize": "13px"}),
                        html.Span(f"{count}", style={
                            "marginLeft": "10px",
                            "backgroundColor": COLORS["red"],
                            "color": "#fff", "borderRadius": "4px",
                            "padding": "2px 10px", "fontSize": "11px",
                            "fontWeight": "700", "fontFamily": FONT_MONO,
                        }),
                    ],
                    style={
                        "display": "inline-flex", "alignItems": "center",
                        "backgroundColor": COLORS["saffron_light"],
                        "borderRadius": "6px", "padding": "10px 16px",
                        "marginRight": "10px", "marginBottom": "10px",
                        "border": f"1px solid {COLORS['saffron']}33",
                    },
                )
            )
        return html.Div(chips, style={"display": "flex", "flexWrap": "wrap"})

    # ── Table status filter ──────────────────────────────────────────
    @app.callback(
        Output("status-filter", "data"),
        Input("filter-all", "n_clicks"),
        Input("filter-pending", "n_clicks"),
        Input("filter-progress", "n_clicks"),
        Input("filter-fixed", "n_clicks"),
        State("status-filter", "data"),
    )
    def update_filter(_a, _b, _c, _d, current):
        trigger = (
            callback_context.triggered[0]["prop_id"].split(".")[0]
            if callback_context.triggered
            else ""
        )
        mapping = {
            "filter-all": "All",
            "filter-pending": "Pending",
            "filter-progress": "In Progress",
            "filter-fixed": "Fixed",
        }
        return mapping.get(trigger, current)

    # ── Live table  <-  /api/potholes logic ──────────────────────────
    @app.callback(
        Output("live-table", "data"),
        Input("refresh", "n_intervals"),
        Input("status-filter", "data"),
    )
    def update_table(_, status_filter):
        records = _data_potholes(limit=50)
        if status_filter != "All":
            records = [r for r in records if r.get("status") == status_filter]
        rows = []
        for r in records:
            row = dict(r)
            link = row.get("maps_link", "#")
            if not link.startswith("[Open Map]"):
                row["maps_link"] = f"[Open Map]({link})"
            rows.append(row)
        return rows