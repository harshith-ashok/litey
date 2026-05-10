from fastmcp import FastMCP
import requests
import json
from pathlib import Path
from datetime import datetime

mcp = FastMCP("Local Voice Assistant")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma4:e4b"
SESSION_FILE = Path(__file__).with_name("conversation_history.json")

SYSTEM_PROMPT = """You are a helpful voice assistant. Respond concisely and accurately:
- Keep responses under 4 sentences when possible
- Be direct and avoid unnecessary details
- If asked a question, provide a clear answer
- If unclear, ask for clarification
- Use simple language for voice interaction"""


def load_session():
    if SESSION_FILE.exists():
        with open(SESSION_FILE, 'r') as f:
            return json.load(f)
    return {"messages": []}


def save_session(session):
    with open(SESSION_FILE, 'w') as f:
        json.dump(session, f, indent=2)


def get_conversation_context(session, limit=5):
    """Get recent conversation context for better responses"""
    messages = session.get("messages", [])[-limit:]
    context = ""
    for msg in messages:
        context += f"{msg['role']}: {msg['content']}\n"
    return context.strip()


@mcp.tool()
def chat(prompt: str) -> str:
    session = load_session()

    # Build context from recent conversation
    context = get_conversation_context(session)
    if context:
        full_prompt = f"Recent conversation:\n{context}\n\nUser: {prompt}"
    else:
        full_prompt = prompt

    # Prepare request with conciseness settings
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": f"{SYSTEM_PROMPT}\n\n{full_prompt}",
            "stream": False,
            # "temperature": 0.3,  # Lower temperature for consistency
            # "top_p": 0.9,
            # "top_k": 40,
        },
        timeout=300
    )
    response.raise_for_status()
    assistant_response = response.json()["response"].strip()

    # Store in session
    session["messages"].append(
        {"role": "user", "content": prompt, "timestamp": datetime.now().isoformat()})
    session["messages"].append(
        {"role": "assistant", "content": assistant_response, "timestamp": datetime.now().isoformat()})

    # Keep only last 20 messages to manage file size
    if len(session["messages"]) > 20:
        session["messages"] = session["messages"][-20:]

    save_session(session)
    return assistant_response


if __name__ == "__main__":
    mcp.run()
