import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

import gradio as gr
import numpy as np
from faster_whisper import WhisperModel
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession

SESSION_FILE = Path(__file__).with_name("conversation_history.json")

whisper_model = None


def initialize_models():
    global whisper_model

    if whisper_model is None:
        whisper_model = WhisperModel("base", compute_type="int8")


def load_session():
    if SESSION_FILE.exists():
        with open(SESSION_FILE, 'r') as f:
            return json.load(f)
    return {"messages": []}


def save_session(session):
    with open(SESSION_FILE, 'w') as f:
        json.dump(session, f, indent=2)


async def query_mcp(prompt):
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("server.py"))],
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("chat", {"prompt": prompt})

            if hasattr(result, "content") and result.content:
                part = result.content[0]
                if hasattr(part, "text"):
                    return part.text

            return str(result)


def transcribe_audio(audio_tuple):
    if audio_tuple is None:
        return ""

    sample_rate, audio_data = audio_tuple

    if audio_data.dtype != np.int16:
        audio_data = np.int16(audio_data / np.max(np.abs(audio_data)) * 32767)

    import tempfile
    import wave

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    with wave.open(temp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())

    try:
        segments, _ = whisper_model.transcribe(temp.name)
        text = " ".join(segment.text for segment in segments).strip()
        return text
    finally:
        Path(temp.name).unlink(missing_ok=True)


def format_conversation_history(session):
    messages = session.get("messages", [])
    history_text = ""

    for msg in messages:
        role = "You" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        timestamp = msg.get("timestamp", "")

        history_text += f"**{role}** ({timestamp[:10]})\n{content}\n\n"

    return history_text if history_text else "No conversation history yet."


def chat_with_voice(user_input, conversation_history):
    initialize_models()

    text_input = user_input.strip() if user_input else ""

    if not text_input:
        return ""

    session = load_session()

    try:
        response = asyncio.run(query_mcp(text_input))
    except Exception as e:
        response = f"Error querying assistant: {e}"

    session["messages"].append({
        "role": "user",
        "content": text_input,
        "timestamp": datetime.now().isoformat()
    })
    session["messages"].append({
        "role": "assistant",
        "content": response,
        "timestamp": datetime.now().isoformat()
    })

    if len(session["messages"]) > 20:
        session["messages"] = session["messages"][-20:]

    save_session(session)

    history_display = format_conversation_history(session)

    return history_display


def clear_history():
    SESSION_FILE.unlink(missing_ok=True)
    return "Conversation history cleared.", "No conversation history yet."


def create_ui():
    with gr.Blocks(title="Litey") as interface:
        gr.Markdown("# Litey")

        with gr.Row():
            with gr.Column():
                text_input = gr.Textbox(
                    placeholder="Type your message...",
                    lines=1,
                    show_label=False
                )

                submit_btn = gr.Button("Send", scale=0)

        history_display = gr.Markdown(
            "No conversation history yet."
        )

        clear_btn = gr.Button("Clear", variant="stop", scale=0)

        conversation_state = gr.State(load_session())

        def submit_handler(text, history):
            hist = chat_with_voice(text, history)
            return hist, ""

        submit_btn.click(
            submit_handler,
            inputs=[text_input, conversation_state],
            outputs=[history_display, text_input]
        )

        def clear_handler():
            clear_history()
            return "No conversation history yet.", ""

        clear_btn.click(
            clear_handler,
            outputs=[history_display, text_input]
        )

        text_input.submit(
            submit_handler,
            inputs=[text_input, conversation_state],
            outputs=[history_display, text_input]
        )

    return interface


if __name__ == "__main__":
    initialize_models()

    print("Initializing Litey...")
    print("Model loaded")

    interface = create_ui()
    interface.launch(share=False, server_name="127.0.0.1", server_port=7860)
