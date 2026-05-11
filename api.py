from fastapi import FastAPI
from pydantic import BaseModel
from typing import Union, Literal
from pathlib import Path
from datetime import datetime
import json

app = FastAPI(title="Local Device Control Server")

STATE_FILE = Path(__file__).with_name("device_state.json")


class ControlRequest(BaseModel):
    object: str
    action: Union[Literal["on", "off", "red", "green", "blue"], int]


DEFAULT_DEVICES = {
    "Main Light": {
        "object": "Main Light",
        "actions": [
            "on",
            "off"
        ],
        "alias": [
            "bulb",
            "tube light",
            "main lights"
        ],
        "type": "digital",
        "state": {
            "state": "off"
        }
    },
    "Ceiling Fan": {
        "object": "Ceiling Fan",
        "actions": [
            "on",
            "off",
            {
                "range": {
                    "min": 0,
                    "max": 100
                }
            }
        ],
        "alias": [
            "fan",
            "ceiling fan"
        ],
        "type": "analog",
        "state": {
            "power": "off",
            "value": 0
        }
    },
    "Accent Light": {
        "object": "Accent Light",
        "actions": [
            "on",
            "off",
            "red",
            "green",
            "blue"
        ],
        "alias": [
            "accent light",
            "small light"
        ],
        "type": "digital",
        "state": {
            "state": "off",
            "color": None
        }
    }
}


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            return json.load(f)

    state = {
        "devices": DEFAULT_DEVICES,
        "last_updated": None
    }

    save_state(state)
    return state


def save_state(state):
    state["last_updated"] = datetime.now().isoformat()

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def find_device(name: str):
    state = load_state()
    devices = state["devices"]

    name = name.strip().lower()

    for device in devices.values():
        if device["object"].lower() == name:
            return device

        for alias in device["alias"]:
            if alias.lower() == name:
                return device

    return None


@app.get("/devices")
def list_devices():
    state = load_state()
    return {
        "devices": list(state["devices"].values()),
        "last_updated": state["last_updated"]
    }


@app.get("/devices/{device_name}")
def get_device(device_name: str):
    device = find_device(device_name)

    if not device:
        return {
            "success": False,
            "error": f"Unknown device: {device_name}"
        }

    return {
        "success": True,
        "device": device
    }


@app.post("/")
def control_device(request: ControlRequest):
    state = load_state()
    device = find_device(request.object)

    if not device:
        return {
            "success": False,
            "error": f"Unknown device: {request.object}",
            "available_devices": list(state["devices"].keys())
        }

    action = request.action

    if device["type"] == "analog":
        if isinstance(action, int):
            if not 0 <= action <= 100:
                return {
                    "success": False,
                    "error": "Analog values must be between 0 and 100"
                }
            value = action

        elif action == "on":
            value = 100

        elif action == "off":
            value = 0

        else:
            return {
                "success": False,
                "error": f"Invalid action '{action}' for {device['object']}"
            }

        resolved_state = {
            "power": "on" if value > 0 else "off",
            "value": value
        }

        device["state"] = resolved_state

    else:
        allowed_actions = [
            item
            for item in device["actions"]
            if isinstance(item, str)
        ]

        if isinstance(action, int):
            return {
                "success": False,
                "error": f"Numeric values are not allowed for {device['object']}"
            }

        if action not in allowed_actions:
            return {
                "success": False,
                "error": f"Invalid action '{action}' for {device['object']}",
                "allowed_actions": allowed_actions
            }

        resolved_state = {
            "state": action
        }

        if device["object"] == "Accent Light":
            if action in ["red", "green", "blue"]:
                resolved_state["state"] = "on"
                resolved_state["color"] = action
            else:
                resolved_state["color"] = None
        else:
            resolved_state["color"] = None

        device["state"] = resolved_state

    # Persist updated state to device_state.json
    save_state(state)

    return {
        "success": True,
        "request": {
            "object": request.object,
            "action": request.action
        },
        "device": device,
        "resolved_state": resolved_state,
        "last_updated": state["last_updated"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8120)
