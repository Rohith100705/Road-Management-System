# RoadWatch AI: YOLOv8 Pothole Detection System

A real-time, robust pothole detection and verification system built with **YOLOv8** and **Plotly Dash**. This system identifies potholes from live camera feeds, filters out false positives using strict geometry and spatial checks, and alerts users to critical road hazards in real-time.

## Features
- **Real-Time Detection**: Processes live dashcam or webcam video feeds.
- **Robust False-Positive Filtering**: Native configuration ignores standard noise, non-road structures (faces, walls, skylines), and tracks bounding box aspect ratios to prevent false alerts.
- **Buzzer Alert System**: Automatically sounds an alarm when high-severity potholes are detected.
- **Interactive Dashboard**: A built-in Plotly Dash interface for monitoring detections, verifying logs, and checking geospatial density.
- **Geospatial Logging**: Records valid detections directly into a MongoDB database for mapping and tracking road decay.

## Prerequisites
- Python 3.9+
- MongoDB instance (running locally on `localhost:27017` or via cloud URI in `.env`)

## Setup Instructions

1. **Clone the Repository**
   ```bash
   git clone <repository_url>
   cd Road-Management-System
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Create a `.env` file in the root directory:
   ```ini
   MONGO_URI=mongodb://localhost:27017
   MONGO_DB=road_monitoring
   MONGO_COLLECTION=potholes
   FLASK_SECRET_KEY=supersecretkey123

   # Model Paths
   HIGH_MODEL_PATH=models/highpothole.pt
   LOW_MODEL_PATH=models/lessmodel.pt

   # Tuning Parameters
   DEBUG_MODE=False
   CONFIDENCE_THRESHOLD=0.6
   IGNORE_TOP_PERCENTAGE=0.3
   MIN_BBOX_AREA_RATIO=0.001
   MAX_BBOX_AREA_RATIO=0.5
   MAX_ASPECT_RATIO=1.2
   ```

4. **Add Trained Models**
   Due to GitHub size limitations, the YOLO model weights (`.pt` files) are not included. 
   Please download your trained weights and place them inside the `models/` folder as `highpothole.pt`.

5. **Run the Application**
   ```bash
   python app.py
   ```
   Open your browser and navigate to `http://localhost:8050/dashboard/`.
