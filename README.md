# Litey

---

Extemeley simple and light voice assistant that focuses on low latency and average consistency. It's primary purpose is to run in a Jetson Nano or a Intel NUC.

---

## Goals

1. less than one second response time
2. decent speech-to-text conversion
3. basic session based interaction
4. lightweight UI for edge-AI applications

## Packages

```
fastmcp
mcp
requests
openwakeword
faster-whisper
sounddevice
numpy
ai-edge-litert
```

## TODO

- [x] Minimal Fast MCP
- [x] Use gemma3:1b as LLM
- [x] Implement openwakeword

## Wake Word Models

Store these files in [/Users/harshith/Dev/Projects/litey/models](/Users/harshith/Dev/Projects/litey/models):

- `alexa_v0.1.tflite`
- `melspectrogram.tflite`
- `embedding_model.tflite`

The macOS wake-word path now uses `openwakeword` with `ai-edge-litert` instead of ONNX to keep the setup smaller and more reliable.

## Phase 2: Goals

- [ ] Integrate with litey
- [ ] phase out existing
- [ ] deploy on Jetson Nano
