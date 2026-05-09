import queue
import tempfile
import time
import wave

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from openwakeword.model import Model
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp import ClientSession
import asyncio


SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 5
WAKEWORD = "alexa"


def record_audio(seconds=RECORD_SECONDS):
    print("Recording...")
    audio = sd.rec(
        int(seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16"
    )
    sd.wait()

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    with wave.open(temp.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    return temp.name


def transcribe(model, filename):
    segments, _ = model.transcribe(filename)
    return " ".join(segment.text for segment in segments).strip()


async def query_mcp(prompt):
    server = StdioServerParameters(command="python", args=["server.py"])

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("chat", {"prompt": prompt})

            if hasattr(result, "content") and result.content:
                part = result.content[0]
                if hasattr(part, "text"):
                    return part.text

            return str(result)


def listen_for_wakeword():
    print("Loading wake word model...")

    model = Model(
        inference_framework="onnx"
    )

    available = list(model.models.keys())
    print("Available wake words:", available)

    if not available:
        raise RuntimeError(
            "No ONNX wake word models were found. "
            "Reinstall with: pip install --force-reinstall openwakeword onnxruntime"
        )

    wakeword = available[0]
    print(f"Listening for wake word: {wakeword}")

    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        q.put(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=1280,
        callback=callback,
    ):
        while True:
            audio = q.get()
            samples = audio.flatten()

            predictions = model.predict(samples)
            score = predictions.get(wakeword, 0.0)

            if score > 0.5:
                print("Wake word detected!")
                return

            time.sleep(0.01)


def main():
    whisper = WhisperModel("base", compute_type="int8")

    print("Voice assistant ready.")
    print("Press Enter to speak, or Ctrl+C to exit.")

    while True:
        input("\nPress Enter and start speaking...")

        wav_file = record_audio()
        text = transcribe(whisper, wav_file)

        if not text:
            print("Could not understand speech.")
            continue

        print(f"You said: {text}")

        response = asyncio.run(query_mcp(text))
        print(f"Assistant: {response}")


if __name__ == "__main__":
    main()
