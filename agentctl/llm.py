# agentctl/llm.py
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def ask_llm(prompt: str, model="gpt-4.1"):
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return res.choices[0].message.content
