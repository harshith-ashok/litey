from fastapi import FastAPI
from pydantic import BaseModel
from typing import Union, Literal

app = FastAPI(title="Local Device Control Server")


class ControlRequest(BaseModel):
    object: str
    action: Union[Literal["on", "off", "red", "green", "blue"], int]


DEVICES = {
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
        "type": "digital"
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
        "type": "analog"
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
        "type": "digital"
    }
}


def find_device(name: str):
    name = name.strip().lower()

    for device in DEVICES.values():
        if device["object"].lower() == name:
            return device

        for alias in device["alias"]:
            if alias.lower() == name:
                return device

    return None


@app.get("/devices")
def list_devices():
    return {
        "devices": list(DEVICES.values())
    }


@app.post("/")
def control_device(request: ControlRequest):
    device = find_device(request.object)

    if not device:
        return {
            "success": False,
            "error": f"Unknown device: {request.object}",
            "available_devices": [device["object"] for device in DEVICES.values()]
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

    else:
        allowed_actions = [
            action
            for action in device["actions"]
            if isinstance(action, str)
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

    return {
        "success": True,
        "request": {
            "object": request.object,
            "action": request.action
        },
        "device": {
            "object": device["object"],
            "alias": device["alias"],
            "type": device["type"],
            "actions": device["actions"]
        },
        "resolved_state": resolved_state
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8120)
