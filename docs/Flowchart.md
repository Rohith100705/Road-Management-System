# RoadWatch AI - System Architecture & Data Flow

This document details the **Asynchronous Computer Vision & Geospatial Telemetry Pipeline** that powers RoadWatch AI.

## 🚀 Architectural Blueprint

The system utilizes a multi-stage lifecycle to transform raw visual telemetry into actionable infrastructure intelligence.

```mermaid
graph TD
    subgraph S1 ["1. EDGE INFERENCE"]
        CAM["Live Video Ingestion<br/>(Dashcam / Mobile Feed)"]
        DET["YOLOv11 Inference Pipeline<br/>(Real-time Object Detection)"]
    end

    subgraph S2 ["2. SPATIO-TEMPORAL SYNTHESIS"]
        GPS["Precision Geolocation Capture<br/>(Lat / Long Metadata)"]
        GEO["Reverse Geocoding Layer<br/>(Google Maps API Envrichment)"]
        API["RESTful API Gateway<br/>(Flask Payload Handling)"]
    end

    subgraph S3 ["3. ANALYTICS & PERSISTENCE"]
        DB["Distributed NoSQL Persistence<br/>(MongoDB Cluster)"]
        DASH["Real-time Telemetry Dashboard<br/>(Plotly Dash Visualization)"]
    end

    CAM -->|Frame Serialization| DET
    DET -->|Detection Metadata| GPS
    GPS -->|Enriched Coordinates| GEO
    GEO -->|Structured Payload| API
    API -->|Asynchronous Ingestion| DB
    DB -->|Reactive Data Surface| DASH

    style S1 fill:#f0f9ff,stroke:#0ea5e9,stroke-width:2px
    style S2 fill:#f0fdf4,stroke:#22c55e,stroke-width:2px
    style S3 fill:#fff7ed,stroke:#f97316,stroke-width:2px
```

## 🛠️ Technical Process Decomposition

1.  **Computer Vision Ingestion**: Real-time video streams (dashcam or mobile) are fed into the high-performance YOLOv11 inference pipeline for localized defect detection.
2.  **Inference & Classification**: Our optimized deep learning model identifies infrastructure hazards (potholes, cracks, etc.) with high precision and low edge latency.
3.  **Spatio-Temporal Enrichment**: Detection events are instantly correlated with high-precision GPS telemetry, capturing the exact geographic coordinates of each infrastructure defect.
4.  **Geographic Resolver**: Automated reverse geocoding via the Google Maps Platform translates raw coordinates into human-readable municipal addresses for actionable reporting.
5.  **Asynchronous Data Ingestion**: Structured data payloads (hazard snapshots, location metadata, and severity rankings) are securely ingested via the Flask REST API.
6.  **Distributed Persistence & Visualization**: Aggregated data is persisted in a MongoDB cluster and surfaced via a real-time Plotly Dash dashboard for interactive heatmapping and decision support.

---

### **INGRESS → INFERENCE → INSIGHTS**
