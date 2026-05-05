from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import cv2
try:
    from ultralytics import YOLO
except ImportError:  # pragma: no cover - optional dependency fallback
    YOLO = None

from config import Config


MODEL: YOLO | None = None
MODEL_NAME = "Unavailable"
MODEL_ERROR = ""
COLORS = [(56, 189, 248), (249, 115, 22), (34, 197, 94), (239, 68, 68), (234, 179, 8)]


def ensure_output_dir() -> None:
    """Ensure that the annotated frame output directory exists."""
    Config.STATIC_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def _resolve_model_path(raw_path: str | None) -> Path | None:
    """Resolve a model path from config into an absolute path."""
    if not raw_path:
        return None
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = Config.STATIC_IMAGE_DIR.parent.parent / candidate
    return candidate


def load_model() -> YOLO:
    """Load the primary YOLO model and fall back to the secondary one if needed."""
    global MODEL, MODEL_NAME, MODEL_ERROR
    if MODEL is not None:
        return MODEL
    if YOLO is None:
        MODEL_ERROR = "ultralytics is not installed in the active Python environment"
        raise RuntimeError(MODEL_ERROR)

    candidates = [
        ("HighAccurate Model.pt", _resolve_model_path(Config.HIGH_MODEL_PATH)),
        ("LessAccurate Model.pt", _resolve_model_path(Config.LOW_MODEL_PATH)),
    ]
    errors: List[str] = []
    for name, path in candidates:
        if path is None or not path.exists():
            errors.append(f"{name} missing at {path}")
            continue
        try:
            MODEL = YOLO(str(path), task="detect")
            MODEL_NAME = path.name
            print(f"[YOLO] Loaded model: {MODEL_NAME}")
            return MODEL
        except Exception as exc:
            errors.append(f"{name}: {exc}")

    MODEL_ERROR = "; ".join(errors)
    raise RuntimeError(f"Unable to load any YOLO model. {MODEL_ERROR}")


def calculate_severity(confidence: float, label: str = "Pothole") -> str:
    """Estimate hazard severity from the detection confidence and label."""
    normalized = label.lower()
    if "pothole" in normalized and confidence >= 0.8:
        return "High"
    if confidence >= 0.6:
        return "Medium"
    return "Low"


def annotate_frame(frame, bbox: List[int], label: str, confidence: float):
    """Draw a bounding box and label on the frame."""
    x1, y1, x2, y2 = bbox
    color = COLORS[0]
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"{label} {confidence:.2f}"
    cv2.putText(frame, text, (x1, max(20, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    return frame


def save_annotated_frame(frame) -> str:
    """Save an annotated frame under static/images using a timestamped filename."""
    ensure_output_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = Config.STATIC_IMAGE_DIR / f"frame_{timestamp}.jpg"
    cv2.imwrite(str(output_path), frame)
    return str(output_path.relative_to(Config.STATIC_IMAGE_DIR.parent.parent)).replace("\\", "/")


def detect_frame(frame, confidence_threshold: float | None = None) -> Dict[str, Any]:
    """Run pothole detection on a single frame and return the requested payload."""
    try:
        model = load_model()
    except Exception as e:
        timestamp = datetime.now().isoformat()
        if Config.DEBUG_MODE:
            print(f"[ERROR] Detection failed: {e}")
        return {
            "detected": False,
            "confidence": 0.0,
            "bbox": [],
            "image_path": "",
            "annotated_frame": frame,
            "timestamp": timestamp,
            "severity": "Low",
        }
        
    threshold = confidence_threshold if confidence_threshold is not None else Config.CONFIDENCE_THRESHOLD
    h, w, _ = frame.shape
    results = model(frame, conf=threshold, verbose=False)
    boxes = results[0].boxes
    best = None
    
    min_area = w * h * Config.MIN_BBOX_AREA_RATIO
    max_area = w * h * Config.MAX_BBOX_AREA_RATIO

    reasons = {
        "top": 0,
        "min_area": 0,
        "max_area": 0,
        "aspect": 0,
        "kept": 0
    }

    for idx in range(len(boxes)):
        confidence = float(boxes[idx].conf.item())
        xyxy = boxes[idx].xyxy.cpu().numpy().squeeze().astype(int).tolist()
        x1, y1, x2, y2 = xyxy
        
        # 1. Filter: Ignore top percentage of image (e.g., sky, horizon)
        center_y = (y1 + y2) / 2
        if center_y < h * Config.IGNORE_TOP_PERCENTAGE:
            reasons["top"] += 1
            continue
            
        # 2. Filter: Ignore very small bounding boxes (noise)
        bbox_area = (x2 - x1) * (y2 - y1)
        if bbox_area < min_area:
            reasons["min_area"] += 1
            continue

        # 3. Filter: Ignore very large bounding boxes (e.g., face close to camera)
        if bbox_area > max_area:
            reasons["max_area"] += 1
            continue
            
        # 4. Filter: Aspect Ratio (Height / Width). Potholes are usually wider.
        bbox_width = max(1, x2 - x1)  # Prevent division by zero
        bbox_height = y2 - y1
        aspect_ratio = bbox_height / bbox_width
        if aspect_ratio > Config.MAX_ASPECT_RATIO:
            reasons["aspect"] += 1
            continue

        reasons["kept"] += 1
        label = str(model.names[int(boxes[idx].cls.item())])
        candidate = {
            "confidence": confidence,
            "bbox": xyxy,
            "label": label
            }
        if best is None or candidate["confidence"] > best["confidence"]:
            best = candidate

    if Config.DEBUG_MODE:
        print(f"[DEBUG] Total Detections: {len(boxes)} | Stats: {reasons}")

    timestamp = datetime.now().isoformat()
    
    # Render frame and debug info
    annotated = frame.copy()
    if best is not None:
        annotated = annotate_frame(annotated, best["bbox"], best["label"], best["confidence"])
        
    if Config.DEBUG_MODE:
        filtered = len(boxes) - reasons["kept"]
        cv2.putText(annotated, f"Total: {len(boxes)} | Filtered: {filtered} | Kept: {reasons['kept']}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    if best is None:
        return {
            "detected": False,
            "confidence": 0.0,
            "bbox": [],
            "image_path": "",
            "annotated_frame": annotated,
            "timestamp": timestamp,
            "severity": "Low",
        }

    image_path = save_annotated_frame(annotated)
    return {
        "detected": True,
        "confidence": round(best["confidence"], 4),
        "bbox": best["bbox"],
        "image_path": image_path,
        "annotated_frame": annotated,
        "timestamp": timestamp,
        "severity": calculate_severity(best["confidence"], best["label"]),
    }


def run_image_test(image_path: str) -> Dict[str, Any]:
    """Run detection against a test image and print the result."""
    image = cv2.imread(image_path)
    if image is None:
        result = {"detected": False, "error": f"Unable to read image: {image_path}"}
        print(f"[YOLO][TEST][IMAGE] {result}")
        return result
    try:
        result = detect_frame(image)
    except Exception as exc:
        result = {"detected": False, "error": str(exc)}
    printable = {k: v for k, v in result.items() if k != "annotated_frame"}
    print(f"[YOLO][TEST][IMAGE] {printable}")
    return result


def run_video_test(video_path: str, max_frames: int = 25) -> List[Dict[str, Any]]:
    """Run frame-by-frame detection on a test video and print the results."""
    capture = cv2.VideoCapture(video_path)
    results: List[Dict[str, Any]] = []
    frame_index = 0
    while capture.isOpened() and frame_index < max_frames:
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        try:
            result = detect_frame(frame)
        except Exception as exc:
            result = {"detected": False, "error": str(exc)}
        printable = {k: v for k, v in result.items() if k != "annotated_frame"}
        printable["frame"] = frame_index
        print(f"[YOLO][TEST][VIDEO] {printable}")
        results.append(printable)
        frame_index += 1
    capture.release()
    return results


def get_model_status() -> Dict[str, Any]:
    """Return current model load status for health and startup checks."""
    try:
        load_model()
        return {"loaded": True, "model_name": MODEL_NAME, "error": ""}
    except Exception as exc:
        return {"loaded": False, "model_name": MODEL_NAME, "error": str(exc)}


if __name__ == "__main__":
    if Config.TEST_IMAGE_PATH.exists():
        run_image_test(str(Config.TEST_IMAGE_PATH))
    else:
        print(f"[YOLO][TEST][IMAGE] Missing test image: {Config.TEST_IMAGE_PATH}")

    if Config.TEST_VIDEO_PATH.exists():
        run_video_test(str(Config.TEST_VIDEO_PATH))
    else:
        print(f"[YOLO][TEST][VIDEO] Missing test video: {Config.TEST_VIDEO_PATH}")
