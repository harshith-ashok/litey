import queue
import sys
import tempfile
import time
import wave
from pathlib import Path

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
WAKEWORD_THRESHOLD = 0.5
MODEL_DIR = Path(__file__).with_name("models")
WAKEWORD_MODEL = MODEL_DIR / f"{WAKEWORD}_v0.1.tflite"
MELSPEC_MODEL = MODEL_DIR / "melspectrogram.tflite"
EMBEDDING_MODEL = MODEL_DIR / "embedding_model.tflite"


def create_wakeword_detector():
    required_files = [WAKEWORD_MODEL, MELSPEC_MODEL, EMBEDDING_MODEL]
    missing_files = [path.name for path in required_files if not path.exists()]

    if missing_files:
        raise RuntimeError(
            "Missing wake word model files in "
            f"{MODEL_DIR}: {', '.join(missing_files)}. "
            "Add the openWakeWord .tflite models there before starting the assistant."
        )

    return Model(
        wakeword_models=[str(WAKEWORD_MODEL)],
        melspec_model_path=str(MELSPEC_MODEL),
        embedding_model_path=str(EMBEDDING_MODEL),
        inference_framework="tflite",
    )


def get_wakeword_label(detector):
    return next(iter(detector.models))


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


def listen_for_wakeword(detector, threshold=WAKEWORD_THRESHOLD):
    detector.reset()
    wakeword_label = get_wakeword_label(detector)
    print(f"Listening for wake word: {WAKEWORD}")
    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status)
        q.put(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=1280,
        callback=callback,
    ):
        while True:
            audio = q.get()
            samples = np.asarray(audio, dtype=np.int16).reshape(-1)

            predictions = detector.predict(samples)
            score = predictions.get(wakeword_label, 0.0)

            if score >= threshold:
                print("Wake word detected!")
                return

            time.sleep(0.01)


def main():
    whisper = WhisperModel("base", compute_type="int8")
    wakeword_detector = create_wakeword_detector()

    print("Voice assistant ready.")
    print(f"Say '{WAKEWORD}' to start, or Ctrl+C to exit.")

    while True:
        listen_for_wakeword(wakeword_detector)

        wav_file = record_audio()
        try:
            text = transcribe(whisper, wav_file)
        finally:
            Path(wav_file).unlink(missing_ok=True)

        if not text:
            print("Could not understand speech.")
            continue

        print(f"You said: {text}")

        response = asyncio.run(query_mcp(text))
        print(f"Assistant: {response}")


if __name__ == "__main__":
    main()
