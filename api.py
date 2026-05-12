from fastapi import FastAPI
from pydantic import BaseModel
from typing import Union, Literal
from pathlib import Path
from datetime import datetime
import json

app = FastAPI(title="Smart Home Control API")

STATE_FILE = Path(__file__).with_name("device_state.json")


class ControlRequest(BaseModel):
    object: str
    action: Union[Literal["on", "off", "red", "green", "blue"], int]


DEFAULT_STATE = {
    "devices": {
        "Main Light": {
            "status": 0
        },
        "Ceiling Fan": {
            "status": 0,
            "value": 0
        },
        "Accent Light": {
            "status": 0,
            "color": "red"
        }
    },
    "detected_objects": [],
    "last_updated": None
}


ALIASES = {
    "main light": "Main Light",
    "bulb": "Main Light",
    "tube light": "Main Light",
    "main lights": "Main Light",
    "ceiling fan": "Ceiling Fan",
    "fan": "Ceiling Fan",
    "accent light": "Accent Light",
    "small light": "Accent Light"
}


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            state = json.load(f)

        if "detected_objects" not in state:
            state["detected_objects"] = []

        if "last_updated" not in state:
            state["last_updated"] = None

        return state

    save_state(DEFAULT_STATE.copy())
    return load_state()


def save_state(state):
    state["last_updated"] = datetime.now().isoformat()

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def resolve_device(name: str):
    key = name.strip().lower()

    if key in ALIASES:
        return ALIASES[key]

    for device in DEFAULT_STATE["devices"]:
        if device.lower() == key:
            return device

    return None


def normalize_detected_objects(objects):
    normalized = []
    seen = set()

    for obj in objects:
        if isinstance(obj, dict):
            label = obj.get("label", "")
        else:
            label = str(obj)

        label = label.strip().lower()

        if not label:
            continue

        if label == "person":
            continue

        if label in seen:
            continue

        seen.add(label)
        normalized.append(label)

    return sorted(normalized)


def update_detected_objects(objects):
    state = load_state()
    state["detected_objects"] = normalize_detected_objects(objects)
    save_state(state)
    return state["detected_objects"]


@app.get("/")
def root():
    return {
        "name": "Smart Home Control API",
        "status": "running"
    }


@app.get("/devices")
def list_devices():
    return load_state()


@app.get("/devices/{device_name}")
def get_device(device_name: str):
    state = load_state()

    resolved = resolve_device(device_name)

    if not resolved:
        return {
            "success": False,
            "error": f"Unknown device: {device_name}"
        }

    return {
        "success": True,
        "device": {
            "name": resolved,
            **state["devices"][resolved]
        },
        "detected_objects": state.get("detected_objects", []),
        "last_updated": state.get("last_updated")
    }


@app.get("/objects")
def get_detected_objects():
    state = load_state()

    return {
        "success": True,
        "detected_objects": state.get("detected_objects", []),
        "count": len(state.get("detected_objects", [])),
        "last_updated": state.get("last_updated")
    }


@app.post("/objects")
def set_detected_objects(payload: dict):
    objects = payload.get("objects", [])
    detected_objects = update_detected_objects(objects)

    state = load_state()

    return {
        "success": True,
        "detected_objects": detected_objects,
        "count": len(detected_objects),
        "last_updated": state.get("last_updated")
    }


@app.post("/")
def control_device(request: ControlRequest):
    state = load_state()

    device_name = resolve_device(request.object)

    if not device_name:
        return {
            "success": False,
            "error": f"Unknown device: {request.object}"
        }

    action = request.action
    device = state["devices"][device_name]

    if device_name == "Ceiling Fan":
        if isinstance(action, int):
            value = max(0, min(100, action))
        elif action == "on":
            value = 100
        elif action == "off":
            value = 0
        else:
            return {
                "success": False,
                "error": "Invalid fan action"
            }

        device["value"] = value
        device["status"] = 1 if value > 0 else 0

    elif device_name == "Main Light":
        if action == "on":
            device["status"] = 1
        elif action == "off":
            device["status"] = 0
        else:
            return {
                "success": False,
                "error": "Main Light only supports on/off"
            }

    elif device_name == "Accent Light":
        if action == "on":
            device["status"] = 1
        elif action == "off":
            device["status"] = 0
        elif action in ["red", "green", "blue"]:
            device["status"] = 1
            device["color"] = action
        else:
            return {
                "success": False,
                "error": "Invalid Accent Light action"
            }

    save_state(state)

    return {
        "success": True,
        "device": device_name,
        "action": action,
        "state": device,
        "detected_objects": state.get("detected_objects", []),
        "last_updated": state["last_updated"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8120)
