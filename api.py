# api.py

import os
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

from prompts import SYSTEM_PROMPT
from database import Base, engine, get_db
from models import User
from auth import router as auth_router, get_current_user

# .env dosyasini yukle
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
  raise RuntimeError("OPENAI_API_KEY .env dosyasinda bulunamadi.")

client = OpenAI(api_key=api_key)

# DB tablolarini olustur
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Caption & Hashtag API")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],  # simdilik acik, iste domain'e gore kisitlayabilirsin
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Auth router'i tak
app.include_router(auth_router, prefix="/auth", tags=["auth"])


# ---------- Schemas ----------

class GenerateRequest(BaseModel):
  niche: str = ""
  description: str


class GenerateResponse(BaseModel):
  result: str


# ---------- Business logic ----------

def generate_captions_and_hashtags(description: str, niche: str = "") -> str:
  user_prompt = f"""
Nis: {niche}

Video/Post aciklamasi:
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


# ---------- Endpoints ----------

@app.get("/")
def root():
  return {
    "status": "ok",
    "message": "Caption & Hashtag API calisiyor.",
    "time": datetime.utcnow().isoformat() + "Z",
  }


@app.post("/generate", response_model=GenerateResponse)
def generate(
  req: GenerateRequest,
  current_user: User = Depends(get_current_user),  # sadece login kullanici
  db: Session = Depends(get_db),                   # ileride db kullanirsan hazir
):
  # current_user.id vs. burada mevcut
  result = generate_captions_and_hashtags(
    description=req.description,
    niche=req.niche,
  )
  return GenerateResponse(result=result)
