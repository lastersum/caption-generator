import os

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from prompts import SYSTEM_PROMPT

# .env dosyasını yükle
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY .env dosyasında bulunamadı.")

client = OpenAI(api_key=api_key)

app = FastAPI(title="Caption & Hashtag API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Şimdilik her yerden erişime izin veriyoruz
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
class GenerateRequest(BaseModel):
    niche: str = ""
    description: str


class GenerateResponse(BaseModel):
    result: str


def generate_captions_and_hashtags(description: str, niche: str = "") -> str:
    user_prompt = f"""
Niş: {niche}

Video/Post açıklaması:
\"\"\"{description}\"\"\"    
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
    )

    return response.choices[0].message.content.strip()


@app.get("/")
def root():
    return {"status": "ok", "message": "Caption & Hashtag API çalışıyor."}


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    result = generate_captions_and_hashtags(
        description=req.description,
        niche=req.niche,
    )
    return GenerateResponse(result=result)
