from fastmcp import FastMCP
import requests
import json
import re
from pathlib import Path
from datetime import datetime

mcp = FastMCP("Local Voice Assistant")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:1b"
SESSION_FILE = Path(__file__).with_name("conversation_history.json")
CONTROL_SERVER_URL = "http://localhost:8120"

SYSTEM_PROMPT = """You are a helpful voice assistant. Respond concisely and accurately:
- Keep responses under 4 sentences when possible
- Be direct and avoid unnecessary details
- If asked a question, provide a clear answer
- If unclear, ask for clarification
- Use simple language for voice interaction"""

DEVICES = {
    "main light": "Main Light",
    "bulb": "Main Light",
    "tube light": "Main Light",
    "main lights": "Main Light",
    "ceiling fan": "Ceiling Fan",
    "fan": "Ceiling Fan",
    "accent light": "Accent Light",
    "small light": "Accent Light",
}

ACTIONS = ["on", "off", "red", "green", "blue"]


def load_session():
    if SESSION_FILE.exists():
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    return {"messages": []}


def save_session(session):
    with open(SESSION_FILE, "w") as f:
        json.dump(session, f, indent=2)


def get_conversation_context(session, limit=5):
    messages = session.get("messages", [])[-limit:]
    context = ""

    for msg in messages:
        context += f"{msg['role']}: {msg['content']}\n"

    return context.strip()


def detect_device_command(text):
    text_lower = text.lower()

    device_name = None
    action = None

    for device_key, device_full in DEVICES.items():
        if device_key in text_lower:
            device_name = device_full
            break

    if not device_name:
        return None, None

    # Check for numeric values (e.g. "set fan to 75")
    numbers = re.findall(r"\d+", text_lower)
    if numbers:
        action = int(numbers[0])
    else:
        for act in ACTIONS:
            if act in text_lower:
                action = act
                break

    return device_name, action


def normalize_device_name(name: str) -> str:
    if not name:
        return ""

    normalized = name.strip().lower()
    return DEVICES.get(normalized, name.strip())


def format_device_summary(device):
    """
    Expected device format from API:
    {
        "name": "Ceiling Fan",
        "status": 1,
        "value": 75,
        "color": "red"
    }
    """
    name = device.get("name") or device.get("object")
    status = "ON" if device.get("status", 0) else "OFF"

    if name == "Ceiling Fan":
        value = device.get("value", 0)
        return f"{name} is {status} at {value}%"

    if name == "Accent Light":
        if device.get("status", 0):
            color = device.get("color", "red")
            return f"{name} is {status} ({color})"
        return f"{name} is {status}"

    return f"{name} is {status}"


@mcp.tool()
def chat(prompt: str) -> str:
    """
    Main conversational entry point.
    Automatically detects device control requests and status queries.
    """

    prompt_lower = prompt.lower()

    # Detect status queries
    status_keywords = [
        "status",
        "state",
        "is the",
        "are the",
        "what is the",
        "what's the",
        "which devices",
    ]

    is_status_query = any(
        keyword in prompt_lower for keyword in status_keywords)

    if is_status_query:
        device_name, _ = detect_device_command(prompt)

        if device_name:
            status_result = get_device_status(device_name)
        else:
            status_result = get_device_status()

        try:
            parsed = json.loads(status_result)
            if parsed.get("success"):
                response_msg = parsed.get(
                    "summary", "Status retrieved successfully.")
            else:
                response_msg = parsed.get(
                    "error", "Unable to retrieve device status.")
        except Exception:
            response_msg = status_result

        session = load_session()
        session["messages"].append(
            {
                "role": "user",
                "content": prompt,
                "timestamp": datetime.now().isoformat(),
            }
        )
        session["messages"].append(
            {
                "role": "assistant",
                "content": response_msg,
                "timestamp": datetime.now().isoformat(),
            }
        )
        save_session(session)

        return response_msg

    # Detect device control commands
    device_name, action = detect_device_command(prompt)

    if device_name and action is not None:
        result = control_device(device_name, action)

        try:
            parsed = json.loads(result)
            if parsed.get("success"):
                response_msg = (
                    f"Done! I have set the {device_name.lower()} to {action}."
                )
            else:
                response_msg = parsed.get(
                    "error", "Unable to control the device.")
        except Exception:
            response_msg = (
                f"Done! I have set the {device_name.lower()} to {action}."
            )

        session = load_session()
        session["messages"].append(
            {
                "role": "user",
                "content": prompt,
                "timestamp": datetime.now().isoformat(),
            }
        )
        session["messages"].append(
            {
                "role": "assistant",
                "content": response_msg,
                "timestamp": datetime.now().isoformat(),
            }
        )
        save_session(session)

        return response_msg

    # Normal LLM conversation
    session = load_session()

    context = get_conversation_context(session)
    if context:
        full_prompt = f"Recent conversation:\n{context}\n\nUser: {prompt}"
    else:
        full_prompt = prompt

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": f"{SYSTEM_PROMPT}\n\n{full_prompt}",
            "stream": False,
        },
        timeout=300,
    )
    response.raise_for_status()

    assistant_response = response.json()["response"].strip()

    session["messages"].append(
        {
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().isoformat(),
        }
    )
    session["messages"].append(
        {
            "role": "assistant",
            "content": assistant_response,
            "timestamp": datetime.now().isoformat(),
        }
    )

    if len(session["messages"]) > 20:
        session["messages"] = session["messages"][-20:]

    save_session(session)

    return assistant_response


@mcp.tool()
def get_device_status(object: str = "") -> str:
    """
    Get current device status.

    Examples:
    - get_device_status()              -> all devices
    - get_device_status("Ceiling Fan")
    - get_device_status("fan")
    """

    try:
        # Return all devices
        if not object or not object.strip():
            response = requests.get(
                f"{CONTROL_SERVER_URL}/devices",
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()

            # Supports either:
            # {"devices": {...}}
            # or {"devices": [...]}
            devices_data = data.get("devices", {})
            last_updated = data.get("last_updated")

            if isinstance(devices_data, list):
                devices_list = devices_data
            else:
                devices_list = []
                for name, device in devices_data.items():
                    if isinstance(device, dict):
                        device_copy = dict(device)
                        device_copy.setdefault("name", name)
                        devices_list.append(device_copy)

            summaries = [
                format_device_summary(device)
                for device in devices_list
            ]

            return json.dumps(
                {
                    "success": True,
                    "summary": "\n".join(summaries),
                    "devices": devices_list,
                    "last_updated": last_updated,
                },
                indent=2,
            )

        # Return one device
        resolved_name = normalize_device_name(object)

        response = requests.get(
            f"{CONTROL_SERVER_URL}/devices/{resolved_name}",
            timeout=10,
        )
        response.raise_for_status()

        data = response.json()

        # Supports:
        # {"success": True, "device": {...}}
        # or direct device object
        if isinstance(data, dict) and "device" in data:
            device = data["device"]
        else:
            device = data

        if isinstance(data, dict) and data.get("success") is False:
            return json.dumps(data, indent=2)

        device.setdefault("name", device.get("object", resolved_name))

        return json.dumps(
            {
                "success": True,
                "summary": format_device_summary(device),
                "device": device,
            },
            indent=2,
        )

    except requests.exceptions.ConnectionError:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"Could not connect to control server at "
                    f"{CONTROL_SERVER_URL}"
                ),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
            },
            indent=2,
        )


@mcp.tool()
def control_device(object: str, action) -> str:
    """
    Control a device.

    Examples:
    - control_device("Main Light", "on")
    - control_device("Ceiling Fan", 75)
    - control_device("Accent Light", "red")
    """

    try:
        response = requests.post(
            CONTROL_SERVER_URL,
            json={
                "object": object,
                "action": action,
            },
            timeout=10,
        )
        response.raise_for_status()

        return json.dumps(response.json(), indent=2)

    except requests.exceptions.ConnectionError:
        return json.dumps(
            {
                "success": False,
                "error": (
                    f"Could not connect to control server at "
                    f"{CONTROL_SERVER_URL}"
                ),
            },
            indent=2,
        )

    except Exception as e:
        return json.dumps(
            {
                "success": False,
                "error": str(e),
            },
            indent=2,
        )


if __name__ == "__main__":
    mcp.run()
