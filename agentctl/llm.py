import os
import asyncio
from huggingface_hub import InferenceClient

HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

client = InferenceClient(
    token=HF_TOKEN,
    timeout=120
)

def _hf_call(prompt: str) -> str:
    """
    Safe HF call:
      - Uses chat_completion
      - Cleans code fencing
      - Hard-fails quietly so AgentService can fallback
    """
    try:
        response = client.chat_completion(
            model=HF_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a STRICT Kubernetes generator. "
                        "You MUST always generate minimal, safe YAML.\n"
                        "YOU MUST OBEY:\n"
                        "- Create ONLY simple CPU-only Jobs.\n"
                        "- NEVER use GPU.\n"
                        "- NEVER use PyTorch, TensorFlow, ML training, train.py.\n"
                        "- Allowed images ONLY: busybox OR python:3.10-slim.\n"
                        "- Commands must be simple: echo, sleep, ls.\n"
                        "- Memory <= 256Mi, CPU <= 250m.\n"
                        "- No external registries.\n"
                        "- Must fit in Minikube.\n"
                        "- YAML must ALWAYS be short, valid, deterministic.\n"
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=400,
            temperature=0.2,
            top_p=0.9,
            stream=False
        )

        if not response or not response.choices:
            print("[HF WARNING] Empty response structure")
            return ""

        content = response.choices[0].message.content.strip()

        # -------- Clean ```yaml fencing ----------
        lines = content.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]

        return "\n".join(lines).strip()

    except Exception as e:
        print(f"[HF LLM ERROR] {e}")
        return ""


async def ask_llm(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _hf_call(prompt))
