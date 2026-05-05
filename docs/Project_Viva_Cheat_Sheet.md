# RoadWatch AI - Final Project Viva Cheat Sheet

Use this document to prepare for your final year project presentation/defense. Reviewers focus on **why** you built it this way, and **how** the architecture links together.

---

## 1. The Core Data Pipeline (How it works end-to-end)
* **Step 1 (Edge Client):** The browser uses JavaScript (`navigator.mediaDevices`) to access the webcam. It captures video frames, converts them to Base64 images, and simultaneously grabs GPS coordinates via `navigator.geolocation` (with an IP-based fallback).
* **Step 2 (AI Inference):** The frame is sent via a `POST` request to the Flask backend `/api/detect_frame`. OpenCV decodes the image, passes it to the **YOLOv11** model, and returns a bounding box, severity, and confidence score.
* **Step 3 (Verification Backend):** If a pothole is found, `storage.py` kicks in. It uses a **Haversine Algorithm** to check if the exact same pothole already exists in the database within a 15-meter radius. It merges the data if it exists, or creates a new one.
* **Step 4 (Dashboard Monitoring):** A background polling system in Plotly Dash automatically fetches the updated MongoDB data and recalculates the charts, map, and ranking table in real-time.

## 2. The AI Object Detection Model
**Q: Why did you use YOLO instead of other models (e.g., Faster R-CNN)?**
* **Answer:** You used **YOLO (You Only Look Once)**—specifically via the Ultralytics library utilizing custom trained weights (`highpothole.pt`).
* YOLO was explicitly chosen because it is a "single-stage" detector. It is highly optimized for **real-time edge computing**, providing high Frames Per Second (FPS) with low latency. This is absolutely mandatory when evaluating video live from a moving dashcam, where speed is more critical than analyzing static photos.

## 3. The Backend Verification Logic (Crucial Differentiator!)
**Q: How do you handle false positives and what elevates this beyond a basic detection project?**  
This is the strongest selling point from the abstract. Focus on these three pillars:
* **Spatial Clustering:** The system doesn't blindly insert database rows for every frame. We calculate the geographic distance between detections using the Haversine formula (Earth's curvature). 
* **Continuous Verification (`Tentative` vs `Verified`):** The AI will inevitably misidentify things (e.g., shadows). By refusing to mark a pothole as **`Verified`** until the `detection_count` hits 3 independent camera hits, we eliminate noise mathematically.
* **Dynamic Priority Algorithm:** Ensure the reviewer understands the custom equation running in the background: `Rank = Severity Score + Traffic Frequency + Days Unresolved`.

## 4. The Technology Stack Justifications
**Q: Why did you pick this specific tech stack?**
* **MongoDB (Database):** Chosen because it is a NoSQL Document database. Hardware IoT devices and dashcams send unstructured JSON payloads. MongoDB easily scales and handles live telemetry data incredibly fast without rigid SQL schemas.
* **Flask (Backend/API):** Lightweight, easy to run, and integrates perfectly with data-heavy Python ML libraries like OpenCV and PyTorch/Ultralytics natively.
* **Plotly Dash (Frontend Web):** Selected because it bridges the gap between complex Python data analytics and modern frontend charting, allowing for real-time infrastructure metrics without needing to build and maintain a massive React.js/Node framework.

## 5. Geolocation Routing & Map Logic
**Q: How are you getting physical street names from just camera recordings?**
* **Reverse Geocoding:** The browser provides raw Latitude/Longitude. The `geotagger.py` script takes these coordinates and runs them through a Reverse Geocoder API. 
* **Failover logic:** The backend attempts to hit Google Maps first but has an automatic **OpenStreetMap (Nominatim)** failover. This ensures the dashboard doesn't crash if an API key expires!

---

### Pro-Presentation Tips:
1. **The Live Buzzer Check:** When presenting the "Live Monitoring" camera page, trigger the buzzer deliberately by moving a picture of a pothole aggressively into the camera until it flashes `High` severity. Point out that the browser is doing ADAS (Advanced Driver Assistance Systems) audio alerts while silently sending telemetry to the main portal!
2. **The Auto-Resolver:** Mention the background script that auto-resolves potholes if they haven't been detected in 48 hours—it shows you thought about the entire "lifecycle" of municipal maintenance, not just detection.
