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
onnxruntime
faster-whisper
sounddevice
numpy
```

## TODO

- [x] Minimal Fast MCP
- [x] Use gemma3:1b as LLM
- [ ] Implement openwakeword
