from fastmcp import FastMCP
import requests
import json
import re
from pathlib import Path
from datetime import datetime

mcp = FastMCP("Local Voice Assistant")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"
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
    "ceiling fan": "Ceiling Fan",
    "fan": "Ceiling Fan",
    "accent light": "Accent Light",
    "small light": "Accent Light",
}

ACTIONS = ["on", "off", "red", "green", "blue"]


def load_session():
    if SESSION_FILE.exists():
        with open(SESSION_FILE, 'r') as f:
            return json.load(f)
    return {"messages": []}


def save_session(session):
    with open(SESSION_FILE, 'w') as f:
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

    numbers = re.findall(r'\d+', text_lower)
    if numbers:
        action = numbers[0]
    else:
        for act in ACTIONS:
            if act in text_lower:
                action = act
                break

    return device_name, action


@mcp.tool()
def chat(prompt: str) -> str:
    device_name, action = detect_device_command(prompt)

    if device_name and action:
        result = control_device(device_name, action)
        response_msg = f"Done! I have set the {device_name.lower()} to {action}"
        session = load_session()
        session["messages"].append(
            {"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()})
        session["messages"].append(
            {"role": "assistant", "content": response_msg, "timestamp": datetime.now().isoformat()})
        save_session(session)
        return response_msg

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
        timeout=300
    )
    response.raise_for_status()
    assistant_response = response.json()["response"].strip()

    session["messages"].append(
        {"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()})
    session["messages"].append(
        {"role": "assistant", "content": assistant_response, "timestamp": datetime.now().isoformat()})

    if len(session["messages"]) > 20:
        session["messages"] = session["messages"][-20:]

    save_session(session)
    return assistant_response


@mcp.tool()
def control_device(object: str, action: str) -> str:
    try:
        response = requests.post(
            CONTROL_SERVER_URL,
            json={
                "object": object,
                "action": action
            },
            timeout=10
        )
        response.raise_for_status()
        return json.dumps(response.json())
    except requests.exceptions.ConnectionError:
        return f"Error: Could not connect to control server at {CONTROL_SERVER_URL}"
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
