from fastmcp import FastMCP
import requests

mcp = FastMCP("Local Voice Assistant")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:1b"


@mcp.tool()
def chat(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False
        },
        timeout=300
    )
    response.raise_for_status()
    return response.json()["response"].strip()


if __name__ == "__main__":
    mcp.run()
