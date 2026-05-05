# RoadWatch AI - Academic Project Documentation

## 1. Project Overview

**What the project does:**
RoadWatch AI is a smart, automated road infrastructure monitoring and verification system. It utilizes computer vision (YOLO) to automatically detect road hazards (specifically potholes) in real-time from vehicle dashcams or mobile devices. The system streams this telemetry data to a centralized portal where incidents are geographically clustered, verified using multi-vehicle consensus, and mathematically ranked for priority repair. 

**Target Users:**
* **Municipal Corporations & Civic Authorities:** For monitoring city road health and dispatching repair teams.
* **National Highway Authority of India (NHAI):** To oversee long-stretch infrastructure maintenance.
* **Road Maintenance Contractors:** To receive automated, prioritized work orders.
* **General Public/Drivers:** Benefit indirectly via safer roads and directly via the in-built Advanced Driver Assistance System (ADAS) audio alerts.

**Real-World Problem it Solves:**
Traditional road maintenance relies on manual surveying or citizen complaints, which are slow, subjective, and prone to human error. RoadWatch AI eliminates manual reporting by passively crowd-sourcing telemetry data from moving vehicles. It solves the massive "false positive" problem via intelligent geospatial clustering (determining if multiple cars saw the *same* pothole) rather than blindly logging thousands of distinct complaint tickets for a single deteriorated road patch.

---

## 2. Complete Feature List

1. **Live Camera & Telemetry Streaming:** 
   * *How it works:* An edge client (web browser) hooks into `navigator.mediaDevices` to stream video. It converts frames to Base64 and retrieves the live GPS coordinates (latitude/longitude) using the HTML5 Geolocation API, pinging it to the server.
2. **Real-Time Pothole Detection:**
   * *How it works:* The server processes incoming frames using the YOLO object detection framework to calculate bounding boxes, confidence scores, and basic severity classifications based on AI confidence.
3. **Geospatial Clustering (The Verification Engine):**
   * *How it works:* Every new detection is compared against existing unresolved potholes in the database. Using the Haversine formula, if a detection falls within a 15-meter radius of an existing incident, they are merged.
4. **Multi-Vehicle Consensus:**
   * *How it works:* Freshly detected potholes remain `Tentative`. Only when independent detection hits cross a threshold (e.g., `detection_count >= 3`) does the system upgrade the status to `Verified`, drastically reducing AI false positives (like shadows).
5. **Dynamic Priority Scoring:**
   * *How it works:* A background mathematical algorithm ranks the urgency of a repair (0 to 100) based on three variables: AI-derived Severity, Traffic Frequency (number of detections), and Days Unresolved.
6. **Time-Based Auto-Resolution:**
   * *How it works:* If a previously detected active pothole goes completely undetected by passing vehicles for 48 consecutive hours, the system intelligently infers it has been repaired and transitions the status to `Fixed` (`Auto-Resolved`).
7. **ADAS Audio Buzzer Alert:**
   * *How it works:* If a driver approaches a pothole dynamically classified as `High` severity, the client triggers an HTML5 AudioContext oscillator to buzz the driver.
8. **Real-Time Executive Dashboard & Live Map:**
   * *How it works:* A Plotly Dash frontend automatically polls the backend and constructs dynamic analytic charts, while a Leaflet.js map graphically overlays color-coded severity markers (Red/Orange/Green) on a real-time world map.

---

## 3. Technologies Used

* **Core Application/Backend Tier:** Python 3, Flask
* **Artificial Intelligence / Computer Vision:** Ultralytics YOLOv11 (PyTorch-based), OpenCV (`cv2`), NumPy
* **Frontend Analytics Dashboard:** Plotly Dash (`dash`, `dash-table`), HTML5, CSS3 
* **Frontend Mapping:** Leaflet.js (OpenStreetMap Tiles)
* **Database / Storage:** MongoDB (`pymongo`) with built-in schema-less JSON document support (plus an in-memory Python list fallback).
* **Location Services:** HTML5 Navigator Geolocation, `ip-api.com` (IP fallback), OpenStreetMap Nominatim (Reverse Geocoding fallback).

---

## 4. System Architecture

RoadWatch AI is designed as a modular Client-Server architecture utilizing a centralized REST API and a decoupled background data-processing storage script.

**Components & Data Flow (Input to Output):**
1. **Edge Node (Input):** The driver's device opens `/camera/start`. A javascript loop runs every 1.5 seconds, capturing a video snapshot. It fetches GPS coordinates.
2. **Network Transport:** The snapshot is converted into a compressed Base64 JPEG string. It is packaged with `lat` and `lng` into a JSON payload and `POST`ed to the `/api/detect_frame` Flask endpoint.
3. **Inference Component:** Flask decodes the Base64 image back into an OpenCV matrix (`numpy.ndarray`). The YOLO model processes the matrix, outputting localization bounding boxes and class probabilities.
4. **Data Verification Component:** If a hazard is found, the data is pushed to `storage.py`. The Database engine pulls all active `Pending` or `In Progress` incidents. It iterates through them, calculating the Haversine distance between the incoming GPS coordinate and the existing coordinates.
5. **Storage Component:** Depending on the distance gap, MongoDB processes either an `update_one` (incrementing counters for matched coordinates) or an `insert_one` (creating a new hazard).
6. **Presentation Component (Output):** The Dashboard (Plotly Dash and Leaflet Map) asynchronously polls `/api/potholes`. It re-renders the data layers, providing road authorities with an updated incident log, ranking table, and geographic heatmap.

---

## 5. Algorithms and Logic

### A. The Haversine Formula (Spatial Clustering)
*Logic:* Because the Earth is a sphere, you cannot accurately calculate the distance between GPS coordinates using standard Euclidean distance. The Haversine formula calculates the great-circle geographic distance between two points (Latitude/Longitude) in meters. 
*Pseudocode:*
```pseudo
Function Haversine(lat1, lon1, lat2, lon2):
    R = 6371000  // Earth radius in meters
    delta_lat = Convert_to_Radians(lat2 - lat1)
    delta_lon = Convert_to_Radians(lon2 - lon1)
    a = Sin(delta_lat/2)^2 + Cos(lat1) * Cos(lat2) * Sin(delta_lon/2)^2
    c = 2 * Atan2(Sqrt(a), Sqrt(1-a))
    Return R * c
```

### B. Dynamic Priority Algorithm
*Logic:* Prioritizing road repairs ensures finite authority budgets are spent optimally.
*Pseudocode:*
```pseudo
Function CalculatePriority(pothole):
    severity_score = IF High THEN 30, IF Medium THEN 20, ELSE 10
    traffic_score = Min(pothole.detection_count * 5, 50) 
    days_unresolved = (Current_Time - pothole.timestamp) in Days
    duration_score = Min(days_unresolved * 10, 20)
    
    Total_Rank_Score = severity_score + traffic_score + duration_score
    Return Total_Rank_Score
```

### C. Auto-Resolution Logic
*Logic:* Automating the lifecycle of an incident.
*Pseudocode:*
```pseudo
Function AutoResolve(pothole):
    Time_Since_Last_Detection = Current_Time - pothole.last_detected
    IF pothole.status == "Pending" OR "In Progress":
        IF Time_Since_Last_Detection > 48 Hours:
            pothole.status = "Fixed"
            pothole.verification_status = "Auto-Resolved"
```

---

## 6. Important Code Snippets

**YOLO Inference Engine (from `yolo_detect.py`):**
```python
def detect_frame(frame, confidence_threshold=0.1):
    model = load_model()
    results = model(frame, verbose=False)
    boxes = results[0].boxes
    best = None
    
    # Filter for the highest confidence pothole in the frame
    for idx in range(len(boxes)):
        confidence = float(boxes[idx].conf.item())
        if confidence < confidence_threshold: continue
        
        xyxy = boxes[idx].xyxy.cpu().numpy().squeeze().astype(int).tolist()
        label = str(model.names[int(boxes[idx].cls.item())])
        
        if best is None or confidence > best["confidence"]:
            best = {"confidence": confidence, "bbox": xyxy, "label": label}
            
    # Return payload dict...
```

**Haversine Clustering Implementation (from `storage.py`):**
```python
active_potholes = list(_collection.find({"status": {"$in": ["Pending", "In Progress"]}}))
for existing in active_potholes:
    # 1. Compare new frame GPS with existing database coordinate
    dist = haversine(new_lat, new_lng, float(existing.get("lat", 0)), float(existing.get("lng", 0)))
    
    # 2. If within 15 meters, it is the EXACT same pothole.
    if dist < 15.0: 
        new_count = existing.get("detection_count", 1) + 1
        # 3. Consensus Verification Logic
        new_status = "Verified" if new_count >= 3 else existing.get("verification_status", "Tentative")
        
        _collection.update_one({"_id": existing["_id"]}, {"$set": {
            "detection_count": new_count, 
            "verification_status": new_status, 
            "last_detected": datetime.now()
        }})
        return str(existing["_id"])
```

---

## 7. Implementation Details

* **Single Web Framework Monolith:** 
  The system utilizes Flask as the central gateway. It routes standard web requests (the Map and Dashboard wrappers), whilst seamlessly handling REST JSON endpoints for sensor data ingestion (`/api/detect_frame`).
* **Dashboard Mount:**
  Plotly Dash is traditionally a standalone framework. To allow data exchange efficiently, the Dash app is natively "mounted" onto the Flask WSGI instance (`dash.Dash(..., server=app)`). This bypasses complex inter-process communication overhead.
* **Non-Blocking Architecture considerations:**
  Since OpenCV and PyTorch calculations are CPU/GPU-blocking requests, the client handles sampling at a 1.5-second interval instead of pushing a continuous 30fps video socket stream. This highly optimizes server memory and network bandwidth.
* **Storage Abstraction:**
  The `storage.py` isolates the database queries. If MongoDB fails to connect (`get_client()`), it gracefully degenerates into an in-memory python `list[]`, ensuring the application doesn't completely crash for academic demo purposes.

---

## 8. Output and Results

* **API Endpoints:** 
  Generates machine-readable tracking metrics via endpoints such as `/api/stats` and `/api/potholes`, which act as data feeds for third-party government portals.
* **Persistent Media Storage:** 
  Annotated video frames showing the YOLO bounding boxes are physically generated and timestamped inside the `/static/images/` directory.
* **Live Incident Dashboard:** 
  Produces a fully realized UI highlighting real-time metrics including "Fix Rate %", "Total Detected", and automated incident tables ranked dynamically.
* **Geographic Map:**
  A Leaflet-powered visual map populated heavily with severity-color-coded tooltips demonstrating exact latitudes and longitudes for maintenance dispatchment.
* **Example Output Scenario:**
  1. A civic garbage truck driving at 40 km/h with a webcam encounters a crater.
  2. The system locates it, highlights a Red bounding box, and creates ID `64b5xyz`. Status: `Tentative`.
  3. The next day, a public bus drives over it. ID `64b5xyz` `detection_count` hits 2. 
  4. Later that afternoon, a third car passes. `detection_count` hits 3. Status updates to `Verified`. The `Priority Score` inflates to 85 out of 100.
  5. The dashboard flashes the incident at the top of the queue for the Public Works Department to assign concrete fill.
