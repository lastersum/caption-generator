# api.py
import os
from typing import List, Optional
from datatime import date
from models import User, CaptionUsage
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv

from database import Base, engine, get_db
from models import User
from auth import router as auth_router, get_current_user
from prompts import SYSTEM_PROMPT

# ---------- .env yükle ----------
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

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # İstersek sonra kısıtlarız
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Auth router ----------
# /auth/register, /auth/login, /auth/me
app.include_router(auth_router, prefix="/auth", tags=["auth"])


# ---------- Ortak Schemaler ----------
class GenerateRequest(BaseModel):
    niche: str = ""
    description: str


class GenerateResponse(BaseModel):
    result: str


class UserAdminOut(BaseModel):
    id: int
    email: EmailStr
    plan: str

    class Config:
        from_attributes = True  # SQLAlchemy objesinden Pydantic modele map için


# ---------- Admin güvenlik helper ----------
def require_admin(admin_secret: str = Header(None, alias="x-admin-secret")) -> bool:
    """
    Tüm admin endpoint'lerinde kullanılacak.
    Header: x-admin-secret: <ADMIN_SECRET>
    """
    real_secret = os.getenv("ADMIN_SECRET")
    if not real_secret or admin_secret != real_secret:
        raise HTTPException(status_code=401, detail="Yetkisiz erişim")
    return True


# ---------- Caption üretim mantığı ----------
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


# ---------- Normal endpointler ----------
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


# ---------- ADMIN ENDPOINTLER ----------

@app.get("/admin/users", response_model=List[UserAdminOut])
def admin_list_users(
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),   # x-admin-secret kontrolü
    plan: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """
    Kullanıcı listesi:
    - plan: 'free' veya 'pro' filtresi (opsiyonel)
    - email: kısmi eşleşme (opsiyonel)
    - limit / offset: pagination
    """
    query = db.query(User)

    if plan:
        query = query.filter(User.plan == plan)

    if email:
        # kısmi arama
        query = query.filter(User.email.ilike(f"%{email}%"))

    users = (
        query.order_by(User.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return users


@app.get("/admin/users/{user_id}", response_model=UserAdminOut)
def admin_get_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    """
    ID'ye göre tek kullanıcı getir.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi")
    return user


@app.get("/admin/users/by-email/{email}", response_model=UserAdminOut)
def admin_get_user_by_email(
    email: str,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    """
    Email'e göre tek kullanıcı getir.
    URL'de @ karakteri otomatik encode edilir (örn: d%40gmail.com).
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi")
    return user


@app.post("/admin/set-plan", response_model=UserAdminOut)
def admin_set_plan(
    email: str,
    plan: str,
    db: Session = Depends(get_db),
    _: bool = Depends(require_admin),
):
    """
    Kullanıcının plan'ını güncelle:
    - plan: 'free' veya 'pro'
    Örnek:
    POST /admin/set-plan?email=x%40gmail.com&plan=pro
    Header: x-admin-secret: <ADMIN_SECRET>
    """
    if plan not in ("free", "pro"):
        raise HTTPException(status_code=400, detail="Plan 'free' veya 'pro' olmali")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Kullanici bulunamadi")

    user.plan = plan
    db.commit()
    db.refresh(user)

    return user
