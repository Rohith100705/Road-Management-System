from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2

from utils.reporter import create_and_save_report
from yolo_detect import detect_frame


@dataclass
class GPSProvider:
    """Simple coordinate provider used by the monitoring pipeline."""

    latitude: float = 12.9716
    longitude: float = 77.5946

    def get_coordinates(self) -> Tuple[float, float]:
        """Return the current latitude and longitude."""
        return self.latitude, self.longitude


class RoadHazardMonitor:
    """Reusable monitoring wrapper around the frame detector."""

    def __init__(self, gps_provider: Optional[GPSProvider] = None) -> None:
        self.gps_provider = gps_provider or GPSProvider()

    def detect(self, frame) -> Dict[str, object]:
        """Detect hazards on a single frame."""
        return detect_frame(frame)

    def annotate(self, frame, detection: Dict[str, object]):
        """Return the annotated frame if one was saved, otherwise the original frame."""
        if detection.get("detected") and detection.get("image_path"):
            annotated = cv2.imread(str(detection["image_path"]))
            if annotated is not None:
                return annotated
        return frame

    def process_detection(self, detection: Dict[str, object]) -> Optional[Dict[str, object]]:
        """Save a detected hazard report and return it."""
        if not detection.get("detected"):
            return None

        lat, lng = self.gps_provider.get_coordinates()
        return create_and_save_report(
            lat=lat,
            lng=lng,
            image_path=str(detection["image_path"]),
            severity=str(detection.get("severity", "Medium")),
            confidence=float(detection.get("confidence", 0.0)),
        )

    def process_stream(self, source: str | int = 0) -> List[Dict[str, object]]:
        """Process a video stream and return saved reports."""
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise RuntimeError(f"Unable to open source: {source}")

        reports: List[Dict[str, object]] = []
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            detection = self.detect(frame)
            if detection.get("detected"):
                report = self.process_detection(detection)
                if report:
                    reports.append(report)
        cap.release()
        return reports
