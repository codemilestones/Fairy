from langchain.chat_models import init_chat_model

# Initialize model
import os
from dotenv import load_dotenv
load_dotenv()

MODEL_BASE_URL = os.getenv("MODEL_BASE_URL")
MODEL_API_KEY = os.getenv("MODEL_API_KEY")

def init_model(model: str, temperature=0.0, max_tokens=32000):
    return init_chat_model(
        model=model,
        base_url=MODEL_BASE_URL,
        api_key=MODEL_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens
    )