# Road Management System 🚧

Real-time pothole detection using YOLOv8 with intelligent filtering and buzzer alerts.

## Features
- Real-time detection (camera/video)
- False-positive reduction (confidence + geometric filters)
- Buzzer alert system
- Clean, modular codebase

## Setup
git clone https://github.com/Rohith100705/Road-Management-System.git
cd Road-Management-System
pip install -r requirements.txt

bash git clone https://github.com/Rohith100705/Road-Management-System.git cd Road-Management-System pip install -r requirements.txt 

## Model Setup
Download your trained model and place it here:
models/highpothole.pt

(Model is not included due to size limits.)

## Run
python app.py 

## Notes
- Works best with a connected camera
- Cloud deployment may not support webcam/buzzer features
