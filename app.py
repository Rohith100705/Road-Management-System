from __future__ import annotations

from typing import Any, Dict

from flask import Flask, jsonify, redirect, render_template_string, request
from config import Config
from dashboard import mount_dashboard
from utils.reporter import create_and_save_report
from utils.storage import (
    get_all_potholes,
    get_counts,
    get_hourly_counts,
    get_severity_counts,
    get_status_counts,
    get_zone_counts,
    initialize_storage,
    mark_as_fixed,
    seed_dummy_data,
)
from yolo_detect import get_model_status

import subprocess
import sys
import os

import base64
import numpy as np
import cv2
from yolo_detect import detect_frame


# ══════════════════════════════════════════════════════════════════════
# Camera Page — Jinja2 Template (GoI / Digital India theme)
# Stored as a Python string, rendered via render_template_string.
# No separate HTML file needed.
# ══════════════════════════════════════════════════════════════════════
CAMERA_PAGE_TEMPLATE = r"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700;800&family=Roboto+Mono:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: {{ c.bg }};
            color: {{ c.text }};
            font-family: 'Noto Sans', 'Segoe UI', Arial, sans-serif;
            display: flex; flex-direction: column;
            min-height: 100vh; overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
        }

        /* Tri-colour banner */
        .tricolour {
            position: fixed; top: 0; left: 0; right: 0; height: 5px; z-index: 9999;
            background: linear-gradient(90deg,
                {{ c.saffron }} 0%, {{ c.saffron }} 33.33%,
                #fff 33.33%, #fff 66.66%,
                {{ c.india_green }} 66.66%, {{ c.india_green }} 100%);
        }

        /* Header */
        .header {
            width: 100%; padding: 12px 32px; margin-top: 5px;
            background: {{ c.header_bg }};
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 3px solid {{ c.saffron }};
        }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-icon { font-size: 30px; color: {{ c.saffron }}; line-height: 1; }
        .brand-title { font-size: 20px; font-weight: 800; color: #fff; letter-spacing: 1.5px; }
        .brand-title span { color: {{ c.saffron }}; }
        .brand-sub {
            font-size: 10px; font-weight: 500; color: #94A3B8;
            letter-spacing: 1px; margin-top: 2px;
        }
        .controls { display: flex; gap: 12px; align-items: center; }
        .controls label {
            font-size: 12px; font-weight: 600; color: #CBD5E1;
            letter-spacing: 0.5px;
        }
        select {
            padding: 8px 14px; border-radius: 6px;
            border: 1px solid #334155;
            background: #1E293B; color: #E2E8F0;
            font-family: 'Roboto Mono', monospace; font-size: 12px;
            cursor: pointer; transition: border-color 0.2s;
        }
        select:focus { outline: none; border-color: {{ c.saffron }}; }
        .btn-end {
            background: transparent; color: {{ c.red }};
            padding: 8px 18px; border-radius: 6px;
            border: 1px solid rgba(220, 38, 38, 0.4);
            font-weight: 700; font-size: 11px; letter-spacing: 0.8px;
            cursor: pointer; text-decoration: none;
            transition: all 0.2s;
        }
        .btn-end:hover { background: rgba(220, 38, 38, 0.1); border-color: {{ c.red }}; }

        /* Main stage */
        .main-stage {
            flex: 1; display: flex; justify-content: center; align-items: center;
            width: 100%; padding: 24px 32px;
        }
        .video-wrapper {
            position: relative; display: inline-block;
            max-width: 100%; border-radius: 8px; overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            border: 1px solid {{ c.panel_border }};
            background: #000;
        }
        video { display: block; max-width: 100%; max-height: 72vh; }
        canvas {
            position: absolute; top: 0; left: 0;
            width: 100%; height: 100%; pointer-events: none;
        }

        /* Overlay badges */
        .badge {
            position: absolute; z-index: 10;
            background: rgba(27, 42, 74, 0.9);
            backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
            border-radius: 6px; padding: 8px 14px;
            font-family: 'Roboto Mono', monospace;
            font-weight: 600; font-size: 11px;
            letter-spacing: 0.8px; color: #E2E8F0;
        }
        .badge-status { top: 14px; left: 14px; border-left: 3px solid {{ c.saffron }}; }
        .badge-label  { top: 14px; right: 14px; border-left: 3px solid {{ c.india_green }}; color: {{ c.saffron }}; font-size: 10px; letter-spacing: 1.5px; }
        .badge-count  { bottom: 14px; left: 14px; border-left: 3px solid {{ c.blue }}; }
        .badge-count strong { color: {{ c.india_green }}; font-size: 14px; }
        .badge-time   { bottom: 14px; right: 14px; color: #94A3B8; font-size: 10px; }

        /* Pulse dot */
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .dot {
            width: 7px; height: 7px; border-radius: 50%;
            display: inline-block; margin-right: 7px;
            animation: pulse 1.5s ease-in-out infinite;
        }
        .dot-green { background: {{ c.india_green }}; box-shadow: 0 0 6px {{ c.india_green }}; }
        .dot-red   { background: {{ c.red }};         box-shadow: 0 0 6px {{ c.red }}; }

        /* Footer */
        .footer {
            width: 100%; padding: 10px 32px;
            background: {{ c.header_bg }};
            border-top: 1px solid #334155;
            display: flex; justify-content: space-between; align-items: center;
        }
        .footer span {
            font-size: 10px; letter-spacing: 1.5px; color: #475569;
            font-family: 'Roboto Mono', monospace;
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: {{ c.bg }}; }
        ::-webkit-scrollbar-thumb { background: #9CA3AF; border-radius: 3px; }

        /* Mobile Responsiveness */
        @media (max-width: 600px) {
            .header { flex-direction: column; gap: 10px; align-items: flex-start; padding: 12px 16px; }
            .main-stage { padding: 12px 16px; }
            .controls { flex-wrap: wrap; width: 100%; }
            .controls label { flex: 1 1 100%; margin-bottom: 4px; }
            #camera-select { flex: 1 1 auto; }
            .btn-end { flex: 1 1 100%; text-align: center; margin-top: 8px; }
            .footer { flex-direction: column; gap: 8px; text-align: center; }
            video { max-height: 50vh; }
        }
    </style>
</head>
<body>
    <div class="tricolour"></div>

    <div class="header">
        <div class="brand">
            <span class="brand-icon">☸</span>
            <div>
                <div class="brand-title">ROADWATCH <span>AI</span></div>
                <div class="brand-sub">{{ subtitle }}</div>
            </div>
        </div>
        <div class="controls">
            <label>Camera Source:</label>
            <select id="camera-select"></select>
            <a href="{{ dashboard_url }}" class="btn-end">✕ End Session</a>
        </div>
    </div>

    <div class="main-stage">
        <div class="video-wrapper">
            <video id="videoElement" autoplay playsinline></video>
            <canvas id="overlayCanvas"></canvas>
            <div class="badge badge-status" id="statusText">
                <span class="dot dot-green"></span>INITIALIZING...
            </div>
            <div class="badge badge-label">{{ feed_label }}</div>
            <div class="badge badge-count" id="detectionCounter">
                DETECTIONS: <strong>0</strong>
            </div>
            <div class="badge badge-time" id="timeOverlay"></div>
        </div>
    </div>

    <div class="footer">
        <span>{{ footer_left }}</span>
        <span>{{ footer_right }}</span>
    </div>

    <canvas id="captureCanvas" style="display:none;"></canvas>

    <script>
        /* ── DOM ─────────────────────────────────── */
        const video         = document.getElementById('videoElement');
        const overlay       = document.getElementById('overlayCanvas');
        const captureCanvas = document.getElementById('captureCanvas');
        const ctx           = overlay.getContext('2d');
        const capCtx        = captureCanvas.getContext('2d');
        const camSel        = document.getElementById('camera-select');
        const statusEl      = document.getElementById('statusText');
        const countEl       = document.getElementById('detectionCounter');
        const timeEl        = document.getElementById('timeOverlay');

        let stream = null, loop = null, detections = 0;
        const API  = '{{ detect_url }}';
        const RATE = {{ detect_interval }};

        const DOT_OK  = '<span class="dot dot-green"></span>';
        const DOT_ERR = '<span class="dot dot-red"></span>';
        
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        let lastBuzz = 0;
        function playBuzzer() {
            if (audioCtx.state === 'suspended') audioCtx.resume();
            if (Date.now() - lastBuzz < 1000) return; // 1s cooldown
            lastBuzz = Date.now();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(600, audioCtx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(1200, audioCtx.currentTime + 0.1);
            gain.gain.setValueAtTime(0.5, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
            osc.start();
            osc.stop(audioCtx.currentTime + 0.4);
        }

        function setStatus(msg, err) {
            statusEl.innerHTML = (err ? DOT_ERR : DOT_OK) + msg;
        }

        /* ── Clock ──────────────────────────────── */
        !function tick() {
            const d = new Date();
            timeEl.textContent = d.toLocaleTimeString('en-IN',{hour12:false}) + '  ' + d.toLocaleDateString('en-IN');
            setTimeout(tick, 1000);
        }();

        /* ── Camera enum ────────────────────────── */
        async function init() {
            try {
                await navigator.mediaDevices.getUserMedia({video:true});
                const devs = (await navigator.mediaDevices.enumerateDevices())
                    .filter(d => d.kind==='videoinput');
                camSel.innerHTML = '';
                devs.forEach((d,i) => {
                    const o = document.createElement('option');
                    o.value = d.deviceId;
                    o.text  = d.label || 'Camera '+(i+1);
                    camSel.appendChild(o);
                });
                devs.length ? startCam(devs[0].deviceId) : setStatus('NO CAMERAS',true);
            } catch(e) { setStatus('ACCESS DENIED',true); }
        }

        async function startCam(id) {
            if (stream) stream.getTracks().forEach(t=>t.stop());
            try {
                stream = await navigator.mediaDevices.getUserMedia(
                    {video: id ? {deviceId:{exact:id}} : true});
                video.srcObject = stream;
                setStatus('LIVE STREAM ACTIVE', false);
                video.onloadedmetadata = () => {
                    overlay.width = captureCanvas.width = video.videoWidth;
                    overlay.height = captureCanvas.height = video.videoHeight;
                    if (loop) clearInterval(loop);
                    loop = setInterval(detect, RATE);
                };
            } catch(e) { setStatus('STREAM FAILED',true); }
        }

        camSel.addEventListener('change', e => startCam(e.target.value));

        let currentLat = 17.6868; // Global default fallback
        let currentLng = 83.2185;
        let locFound = false;

        async function fetchIpLocation() {
            try {
                const res = await fetch('http://ip-api.com/json/');
                const data = await res.json();
                if (data.status === 'success') {
                    currentLat = data.lat;
                    currentLng = data.lon;
                    console.log("Using IP-based location fallback:", data.city);
                }
            } catch(e) { console.error("IP fallback failed"); }
        }

        function fetchLocation() {
            if (navigator.geolocation) {
                 navigator.geolocation.getCurrentPosition(pos => {
                      currentLat = pos.coords.latitude;
                      currentLng = pos.coords.longitude;
                      locFound = true;
                 }, err => {
                      if (!locFound) {
                          console.log("Precise location denied/blocked. Trying IP fallback...");
                          fetchIpLocation();
                          locFound = true; // Prevent spamming IP fallback
                      }
                 }, { enableHighAccuracy: true });
            } else {
                 if (!locFound) { fetchIpLocation(); locFound = true; }
            }
        }
        
        fetchLocation();
        setInterval(fetchLocation, 10000); // refresh location every 10 seconds

        /* ── Detection loop ────────────────────── */
        async function detect() {
            if (video.readyState !== video.HAVE_ENOUGH_DATA) return;
            capCtx.drawImage(video, 0, 0, captureCanvas.width, captureCanvas.height);
            const img = captureCanvas.toDataURL('image/jpeg', 0.8);
            try {
                const response = await fetch(API, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        image: img,
                        lat: currentLat,
                        lng: currentLng
                    })
                });
                const r = await response.json();
                
                ctx.clearRect(0, 0, overlay.width, overlay.height);
                if (r.detected && r.bbox) {
                    const [x1,y1,x2,y2] = r.bbox;
                    detections++;
                    countEl.innerHTML = 'DETECTIONS: <strong>'+detections+'</strong>';
                    
                    if (r.severity === 'High') {
                        playBuzzer();
                    }
                    
                    // Box
                    ctx.shadowColor = '{{ c.india_green }}';
                    ctx.shadowBlur = 10;
                    ctx.strokeStyle = '{{ c.india_green }}';
                    ctx.lineWidth = 3;
                    ctx.strokeRect(x1,y1,x2-x1,y2-y1);
                    ctx.shadowBlur = 0;
                    // Label
                    const lbl = r.hazard_type + ' (' + r.confidence.toFixed(2) + ')';
                    ctx.font = '600 15px "Roboto Mono", monospace';
                    const w = ctx.measureText(lbl).width;
                    const ly = Math.max(26, y1-8);
                    ctx.fillStyle = 'rgba(27,42,74,0.88)';
                    ctx.fillRect(x1, ly-16, w+14, 22);
                    ctx.fillStyle = '{{ c.india_green }}';
                    ctx.fillText(lbl, x1+7, ly);
                    // Alert
                    setStatus('DETECTED: '+r.hazard_type.toUpperCase(), true);
                    setTimeout(() => setStatus('LIVE STREAM ACTIVE',false), 1200);
                }
            } catch(e) { console.error('Detect error:', e); }
        }

        init();
    </script>
</body>
</html>
"""

# ── Camera page context — all Python, no HTML escaping needed ────────
CAMERA_COLORS = {
    "bg":           "#F4F6F9",
    "text":         "#374151",
    "saffron":      "#FF9933",
    "india_green":  "#138808",
    "header_bg":    "#1B2A4A",
    "panel_border": "#D1D5DB",
    "red":          "#DC2626",
    "blue":         "#2563EB",
}


def _camera_context() -> dict:
    """Python dict that drives every variable in the camera template."""
    return {
        "title":           "RoadWatch AI — Live Surveillance Session",
        "subtitle":        "Live Surveillance Module · Digital India",
        "feed_label":       "SURVEILLANCE FEED",
        "dashboard_url":    "/dashboard/",
        "detect_url":       "/api/detect_frame",
        "detect_interval":  1500,
        "footer_left":      "ROADWATCH AI  ·  NATIONAL ROAD INFRASTRUCTURE PORTAL",
        "footer_right":     "POWERED BY YOLO v11 · OPENCV · MONGODB",
        "c":                CAMERA_COLORS,
    }


# ══════════════════════════════════════════════════════════════════════
# Flask Application Factory
# ══════════════════════════════════════════════════════════════════════


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.secret_key = Config.FLASK_SECRET_KEY

    initialize_storage()
    seed_dummy_data()
    mount_dashboard(app)
    register_routes(app)

    print("RoadWatch AI Starting...")
    print(f"Model loaded: {get_model_status()}")
    print(f"MongoDB {'connected' if Config.DB_CONNECTED else 'fallback-active'}")
    print(
        f"Google Maps API {'ready' if Config.GOOGLE_MAPS_API_KEY else 'not configured'}"
    )
    print(f"Dashboard: http://localhost:{Config.FLASK_PORT}/dashboard/")
    print(f"API Base:  http://localhost:{Config.FLASK_PORT}/api/")
    return app


def register_routes(app: Flask) -> None:
    """Register all API and health routes."""

    @app.post("/api/report")
    def api_report() -> Any:
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        lat = float(payload.get("lat", 0.0))
        lng = float(payload.get("lng", 0.0))
        image_path = str(payload.get("image_path", "")).strip()
        severity = str(payload.get("severity", "Medium"))
        confidence = float(payload.get("confidence", 0.0))

        if not image_path:
            return jsonify({"error": "image_path is required"}), 400

        report = create_and_save_report(
            lat=lat,
            lng=lng,
            image_path=image_path,
            severity=severity,
            confidence=confidence,
        )
        return jsonify({"status": "saved", "report": report}), 201


    @app.get("/api/potholes")
    def api_potholes() -> Any:
        limit = request.args.get("limit", default=50, type=int)
        potholes = get_all_potholes(limit=limit)
        return jsonify({"count": len(potholes), "potholes": potholes})


    @app.get("/api/stats")
    def api_stats() -> Any:
        counts = get_counts()
        total = counts.get("total", 0)
        fixed = counts.get("fixed", 0)
        fix_rate = round((fixed / total) * 100, 2) if total else 0.0

        return jsonify({
            **counts,
            "fix_rate": fix_rate,
            "hourly": get_hourly_counts(hours=8),
            "zones": get_zone_counts(),
            "status_counts": get_status_counts(),
            "severity_counts": get_severity_counts(),
        })


    @app.post("/api/fix/<pothole_id>")
    def api_fix(pothole_id: str) -> Any:
        updated = mark_as_fixed(pothole_id)
        if not updated:
            return jsonify({"status": "not_found"}), 404
        return jsonify({"status": "updated"})


    @app.get("/api/hotspots")
    def api_hotspots() -> Any:
        zones = get_zone_counts()
        hotspots = [zone for zone in zones if zone.get("count", 0) > 1]
        return jsonify(hotspots)


    @app.get("/api/health")
    def api_health() -> Any:
        return jsonify({
            "status": "ok",
            "db": "connected" if Config.DB_CONNECTED else "fallback",
            "model": get_model_status(),
        })


    @app.post("/api/detect_frame")
    def api_detect_frame() -> Any:
        payload = request.get_json(silent=True) or {}
        image_b64 = payload.get("image", "")
        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        try:
            _, encoded = image_b64.split(",", 1) if "," in image_b64 else ("", image_b64)
            data = base64.b64decode(encoded)
            np_arr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            result = detect_frame(frame)

            if result.get("detected"):
                lat = float(payload.get("lat", 0.0))
                lng = float(payload.get("lng", 0.0))
                report = create_and_save_report(
                    lat=lat,
                    lng=lng,
                    image_path=result["image_path"],
                    severity=result.get("severity", "Medium"),
                    confidence=result.get("confidence", 0.0),
                )
                return jsonify({
                    "detected": True,
                    "hazard_type": report['hazard_type'],
                    "confidence": result['confidence'],
                    "bbox": result['bbox'],
                    "severity": result.get("severity", "Medium")
                })
            else:
                return jsonify({"detected": False})

        except Exception as e:
            return jsonify({"error": str(e)}), 500


    # ✅ Camera Route (FIXED POSITION)
    @app.get("/camera/start")
    def start_camera() -> Any:
        return render_template_string(CAMERA_PAGE_TEMPLATE, **_camera_context())


    # ✅ Leaflet Map Route (NEW)
    @app.get("/map")
    def map_view():
        return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>RoadWatch AI - Live Map</title>

    <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css"/>
    <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>

    <style>
        body { margin: 0; font-family: Arial; }
        #map { height: 100vh; width: 100%; }

        .legend {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 10px;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.2);
            font-size: 12px;
        }
    </style>
</head>
<body>

<div id="map"></div>

<div class="legend">
    <b>Severity</b><br>
    🔴 High<br>
    🟠 Medium<br>
    🟢 Low
</div>

<script>
var map = L.map('map');

// 🌍 Auto detect user location
navigator.geolocation.getCurrentPosition(function(position) {
    var lat = position.coords.latitude;
    var lng = position.coords.longitude;

    map.setView([lat, lng], 14);

    // Mark your location
    L.marker([lat, lng]).addTo(map)
        .bindPopup("📍 You are here")
        .openPopup();

}, function() {
    // ❗ fallback if user denies permission
    map.setView([17.6868, 83.2185], 13);
});

// Map tiles
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
}).addTo(map);

let markers = [];

function loadPotholes() {
    fetch('/api/potholes')
    .then(res => res.json())
    .then(data => {

        markers.forEach(m => map.removeLayer(m));
        markers = [];

        data.potholes.forEach(p => {

            let color;
            if (p.severity === "High") color = "red";
            else if (p.severity === "Medium") color = "orange";
            else color = "green";

            let marker = L.circleMarker([p.lat, p.lng], {
                radius: 8,
                color: color,
                fillOpacity: 0.8
            }).addTo(map);

            marker.bindPopup(`
                <b>${p.hazard_type}</b><br>
                📍 ${p.address}<br>
                ⚠️ Severity: ${p.severity}<br>
                🎯 Confidence: ${p.confidence}<br>
                📌 Status: ${p.status}<br>
                <a href="${p.maps_link}" target="_blank">Open Location</a>
            `);

            markers.push(marker);
        });
    });
}

// Load + refresh
loadPotholes();
setInterval(loadPotholes, 5000);
</script>

</body>
</html>
""")


    @app.get("/")
    def index() -> Any:
        return redirect("/dashboard/")

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False, ssl_context='adhoc')

