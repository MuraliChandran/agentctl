import os
import asyncio
from huggingface_hub import InferenceClient

HF_TOKEN = os.getenv("HF_TOKEN")
HF_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"

client = InferenceClient(token=HF_TOKEN, timeout=120)

def _hf_call(prompt: str) -> str:
    try:
        messages = [
            {"role": "user", "content": prompt}
        ]

        response = client.chat_completion(
            messages,
            model=HF_MODEL, 
            max_tokens=500,
            temperature=0.2, 
            top_p=0.9,
            stream=False
        )
        
        if response and response.choices:
            content = response.choices[0].message.content
            
            # --- CLEANUP LOGIC START ---
            # The model often wraps code in ```yaml ... ```. We must strip this.
            lines = content.strip().splitlines()
            
            # Remove the top line if it starts with ``` (e.g., ```yaml)
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            
            # Remove the bottom line if it is just ```
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            
            return "\n".join(lines).strip()
            # --- CLEANUP LOGIC END ---

        print("[HF WARNING] Received empty response structure.")
        return ""

    except Exception as e:
        print(f"[HF LLM ERROR] {e}")
        return ""

async def ask_llm(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _hf_call(prompt))