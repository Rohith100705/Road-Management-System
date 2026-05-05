from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List

import certifi

from bson import ObjectId
from pymongo import MongoClient
from pymongo.collection import Collection

from config import Config


_client: MongoClient | None = None
_collection: Collection | None = None
_memory_store: List[Dict[str, Any]] = []
_initialized = False


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in meters between two points on the earth."""
    R = 6371000
    phi_1 = math.radians(lat1)
    phi_2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi_1) * math.cos(phi_2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def initialize_storage() -> Collection | None:
    """Initialize the singleton MongoDB connection if possible."""
    global _client, _collection, _initialized
    if _initialized: return _collection
    _initialized = True
    try:
        _client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        _collection = _client[Config.MONGO_DB][Config.MONGO_COLLECTION]
        _collection.create_index("timestamp")
        _collection.create_index("status")
        _collection.create_index("zone")
        Config.DB_CONNECTED = True
        print("[DB] MongoDB connection ready.")
        return _collection
    except Exception as exc:
        Config.DB_CONNECTED = False
        print(f"[DB][WARN] MongoDB unavailable, using in-memory fallback. {exc}")
        _collection = None
        return None


def _normalize_document(document: Dict[str, Any]) -> Dict[str, Any]:
    """Convert Mongo-specific values into JSON-friendly types."""
    payload = dict(document)
    if "_id" in payload: payload["_id"] = str(payload["_id"])
    return payload


def save_pothole(report: dict) -> str:
    """Save report with Spatial Clustering (Multi-Vehicle Verification)."""
    initialize_storage()
    try:
        payload = dict(report)
        payload.setdefault("status", "Pending")
        new_lat = float(payload.get("lat", 0))
        new_lng = float(payload.get("lng", 0))
        now_str = datetime.now().isoformat()
        
        payload["detection_count"] = 1
        payload["verification_status"] = "Tentative"
        payload["last_detected"] = now_str
        payload["priority_score"] = 0
        
        active_potholes = []
        if _collection is not None:
            active_potholes = list(_collection.find({"status": {"$in": ["Pending", "In Progress"]}}))
        else:
            active_potholes = [p for p in _memory_store if p.get("status") in ["Pending", "In Progress"]]
            
        for existing in active_potholes:
            dist = haversine(new_lat, new_lng, float(existing.get("lat", 0)), float(existing.get("lng", 0)))
            if dist < 15.0: # Match if within 15 meters
                new_count = existing.get("detection_count", 1) + 1
                new_status = "Verified" if new_count >= 3 else existing.get("verification_status", "Tentative")
                
                if _collection is not None:
                    _collection.update_one({"_id": existing["_id"]}, {"$set": {
                        "detection_count": new_count, "verification_status": new_status, 
                        "last_detected": now_str, "confidence": max(payload.get("confidence", 0), existing.get("confidence", 0))
                    }})
                else:
                    for mem in _memory_store:
                        if mem.get("_id") == existing["_id"]:
                            mem["detection_count"] = new_count
                            mem["verification_status"] = new_status
                            mem["last_detected"] = now_str
                            mem["confidence"] = max(payload.get("confidence", 0), mem.get("confidence", 0))
                print(f"[VERIFICATION] Clustered with {existing['_id']}. Total Detections={new_count}, Status={new_status}")
                return str(existing["_id"])
                
        if _collection is not None:
            return str(_collection.insert_one(payload).inserted_id)

        report_id = str(ObjectId())
        payload["_id"] = report_id
        _memory_store.append(payload)
        return report_id
    except Exception as exc: print(f"[DB][ERROR] Save failed: {exc}"); raise


def recalculate_scores_and_resolve() -> None:
    """Implement Time-Based Auto-Resolution and Priority Scoring."""
    initialize_storage()
    now = datetime.now()
    
    def process_item(item):
        changed = False
        last_det_str = item.get("last_detected", item.get("timestamp", now.isoformat()))
        try: 
            last_det = datetime.fromisoformat(last_det_str).replace(tzinfo=None)
        except: 
            last_det = now
            
        # 1. Time-Based Validation (Auto-resolve if unseen for 48 hours)
        if item.get("status") in ["Pending", "In Progress"]:
            if (now - last_det).total_seconds() > 172800:
                item["status"] = "Fixed"
                item["verification_status"] = "Auto-Resolved"
                print(f"[VERIFICATION] Auto-resolved {item.get('_id')} due to time window.")
                changed = True

        # 2. Priority Scoring
        sev = item.get("severity", "Low")
        sev_score = 30 if sev == "High" else (20 if sev == "Medium" else 10)
        traffic_score = min(item.get("detection_count", 1) * 5, 50)
        
        try: 
            orig_ts = datetime.fromisoformat(str(item.get("timestamp"))).replace(tzinfo=None)
        except: 
            orig_ts = now
        dur_score = min(((now - orig_ts).total_seconds() / 86400.0) * 10, 20)
        
        new_score = int(sev_score + traffic_score + dur_score)
        if item.get("status") == "Fixed": new_score = 0
            
        if item.get("priority_score", 0) != new_score:
            item["priority_score"] = new_score
            changed = True
        return changed, item

    if _collection is not None:
        for item in list(_collection.find()):
            chg, upd = process_item(item)
            if chg: _collection.update_one({"_id": item["_id"]}, {"$set": {
                "status": upd.get("status", "Pending"), "verification_status": upd.get("verification_status", "Tentative"),
                "priority_score": upd.get("priority_score", 0) }})
    else:
        for i in range(len(_memory_store)):
            chg, upd = process_item(_memory_store[i])
            if chg: _memory_store[i] = upd


def get_all_potholes(limit: int = 50) -> list:
    """Return potholes sorted by Dynamic Priority Score descending."""
    initialize_storage()
    recalculate_scores_and_resolve()
    try:
        if _collection is not None:
            rows = _collection.find().sort("priority_score", -1).limit(limit)
            return [_normalize_document(r) for r in rows]
        return sorted(_memory_store, key=lambda i: i.get("priority_score", 0), reverse=True)[:limit]
    except Exception as exc: print(f"[DB][ERROR] Fetch failed: {exc}"); return []


def get_counts() -> dict:
    """Return {total, pending, fixed, in_progress, high_severity}."""
    try:
        records = get_all_potholes(limit=10000)
        return {
            "total": len(records),
            "pending": sum(1 for item in records if item.get("status") == "Pending"),
            "fixed": sum(1 for item in records if item.get("status") == "Fixed"),
            "in_progress": sum(1 for item in records if item.get("status") == "In Progress"),
            "high_severity": sum(1 for item in records if item.get("severity") == "High"),
        }
    except Exception as exc:
        print(f"[DB][ERROR] Failed to calculate counts: {exc}")
        return {"total": 0, "pending": 0, "fixed": 0, "in_progress": 0, "high_severity": 0}


def get_hourly_counts(hours: int = 8) -> list:
    """Return [{hour: '10:00', count: 5}, ...] for last N hours."""
    try:
        now = datetime.now()
        records = get_all_potholes(limit=10000)
        output = []
        for offset in reversed(range(hours)):
            slot = now - timedelta(hours=offset)
            label = slot.strftime("%H:00")
            count = 0
            for record in records:
                try:
                    ts = datetime.fromisoformat(str(record.get("timestamp")))
                except Exception:
                    continue
                if ts.strftime("%Y-%m-%d %H") == slot.strftime("%Y-%m-%d %H"):
                    count += 1
            output.append({"hour": label, "count": count})
        return output
    except Exception as exc:
        print(f"[DB][ERROR] Failed to calculate hourly counts: {exc}")
        return []


def get_zone_counts() -> list:
    """Return [{zone: 'MG Road', count: 12}, ...] sorted by count."""
    try:
        counts = Counter(str(record.get("zone", "Unknown Zone")) for record in get_all_potholes(limit=10000))
        return [{"zone": zone, "count": count} for zone, count in counts.most_common()]
    except Exception as exc:
        print(f"[DB][ERROR] Failed to calculate zone counts: {exc}")
        return []


def get_status_counts() -> dict:
    """Return {Pending: N, Fixed: N, In Progress: N}."""
    try:
        counts = Counter(str(record.get("status", "Pending")) for record in get_all_potholes(limit=10000))
        return {
            "Pending": counts.get("Pending", 0),
            "Fixed": counts.get("Fixed", 0),
            "In Progress": counts.get("In Progress", 0),
        }
    except Exception as exc:
        print(f"[DB][ERROR] Failed to calculate status counts: {exc}")
        return {"Pending": 0, "Fixed": 0, "In Progress": 0}


def get_severity_counts() -> dict:
    """Return {High: N, Medium: N, Low: N}."""
    try:
        counts = Counter(str(record.get("severity", "Medium")) for record in get_all_potholes(limit=10000))
        return {"High": counts.get("High", 0), "Medium": counts.get("Medium", 0), "Low": counts.get("Low", 0)}
    except Exception as exc:
        print(f"[DB][ERROR] Failed to calculate severity counts: {exc}")
        return {"High": 0, "Medium": 0, "Low": 0}


def mark_as_fixed(pothole_id: str) -> bool:
    """Update status to Fixed. Return True if successful."""
    initialize_storage()
    try:
        if _collection is not None:
            result = _collection.update_one(
                {"_id": ObjectId(pothole_id)},
                {"$set": {"status": "Fixed", "updated_at": datetime.now().isoformat()}},
            )
            return result.modified_count > 0

        for record in _memory_store:
            if str(record.get("_id")) == pothole_id:
                record["status"] = "Fixed"
                record["updated_at"] = datetime.now().isoformat()
                return True
        return False
    except Exception as exc:
        print(f"[DB][ERROR] Failed to mark pothole as fixed: {exc}")
        return False


def seed_dummy_data(count: int = 25):
    """If collection is empty, insert dummy pothole records for testing."""
    try:
        if get_all_potholes(limit=1):
            return

        base_time = datetime.now()
        zones = ["MG Road", "Indiranagar", "Jayanagar", "Whitefield", "Koramangala"]
        severities = ["High", "Medium", "Low"]
        statuses = ["Pending", "In Progress", "Fixed"]
        for index in range(count):
            lat = 12.9716 + (index * 0.0001)
            lng = 77.5946 + (index * 0.0001)
            save_pothole(
                {
                    "hazard_type": "Pothole",
                    "lat": lat,
                    "lng": lng,
                    "address": f"{zones[index % len(zones)]} Main Road, Bengaluru",
                    "zone": zones[index % len(zones)],
                    "maps_link": f"https://www.google.com/maps/search/?api=1&query={lat},{lng}",
                    "image_path": "static/images/dummy.jpg",
                    "severity": severities[index % len(severities)],
                    "confidence": round(0.55 + ((index % 4) * 0.1), 2),
                    "status": statuses[index % len(statuses)],
                    "timestamp": (base_time - timedelta(minutes=index * 15)).isoformat(),
                }
            )
        print(f"[DB] Seeded {count} dummy pothole records.")
    except Exception as exc:
        print(f"[DB][ERROR] Failed to seed dummy data: {exc}")