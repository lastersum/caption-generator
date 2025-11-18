# api.py
import os
from datetime import date

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv

from database import Base, engine, get_db
from models import User, CaptionUsage
from auth import router as auth_router, get_current_user
from prompts import SYSTEM_PROMPT

# ---------- .env yükle ----------
# .env dosyası api.py ile aynı klasörde olmalı (C:\Users\Murat\Desktop\caption_app\.env)
load_dotenv()

# ---------- DB tablolarını oluştur ----------
Base.metadata.create_all(bind=engine)

# ---------- OpenAI client ----------
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("OPENAI_API_KEY .env dosyasından okunamadı.")

client = OpenAI(api_key=api_key)

# ---------- FastAPI app ----------
app = FastAPI(title="Caption & Hashtag API")

# CORS (Netlify + local geliştirme için şimdilik geniş)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth router'ı bağla → /auth/register, /auth/login, /auth/me
app.include_router(auth_router, prefix="/auth", tags=["auth"])


# ---------- Schemaler (caption için) ----------
class GenerateRequest(BaseModel):
    niche: str = ""
    description: str


class GenerateResponse(BaseModel):
    result: str


# ---------- İş mantığı ----------
def generate_captions_and_hashtags(description: str, niche: str = "") -> str:
    """
    Caption & hashtag üretimi için OpenAI çağrısı.
    """
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


# ---------- Endpointler ----------
@app.get("/")
def root():
    return {"status": "ok", "message": "Caption & Hashtag API calisiyor."}


@app.post("/generate", response_model=GenerateResponse)
def generate(
    req: GenerateRequest,
    current_user: User = Depends(get_current_user),  # 🔐 JWT zorunlu
    db: Session = Depends(get_db),
):
    """
    Caption & hashtag üretimi.
    - Bu endpoint'e erişmek için Authorization: Bearer <token> şart.
    - plan = "free" ise günde 1 kullanım hakkı.
    - plan = "pro" ise sınırsız.
    """
    if not req.description.strip():
        raise HTTPException(status_code=400, detail="description bos olamaz.")

    # ---------- Free plan için günlük limit kontrolü ----------
    usage = None
    if getattr(current_user, "plan", "free") == "free":
        today = date.today()
        usage = (
            db.query(CaptionUsage)
            .filter(
                CaptionUsage.user_id == current_user.id,
                CaptionUsage.date == today,
            )
            .first()
        )

        if usage and usage.count >= 1:
            # Free kullanıcı bugün zaten 1 kez kullanmış
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free planda gunde 1 caption uretebilirsin. Daha fazlasi icin pro plana gec.",
            )

    # ---------- Caption üret ----------
    result_text = generate_captions_and_hashtags(
        description=req.description,
        niche=req.niche or "",
    )

    # ---------- Kullanım kaydı güncelle (sadece free için) ----------
    if getattr(current_user, "plan", "free") == "free":
        today = date.today()
        if not usage:
            usage = CaptionUsage(
                user_id=current_user.id,
                date=today,
                count=0,
            )
            db.add(usage)

        usage.count += 1
        db.commit()
        db.refresh(usage)

    return GenerateResponse(result=result_text)
