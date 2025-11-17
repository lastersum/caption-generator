import os
from models import User
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI
from prompts import SYSTEM_PROMPT
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from auth import hash_password, verify_password, create_access_token, decode_token
from pydantic import BaseModel, EmailStr
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")  # sadece dokumantasyon icin

def get_current_user(token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> User:
    payload = decode_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Gecersiz token.")
    user_id = int(payload["sub"])
    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Kullanici bulunamadi.")
    return user

@app.get("/auth/me", response_model=UserInfo)
def me(current_user: User = Depends(get_current_user)):
    return UserInfo(id=current_user.id, email=current_user.email)

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/auth/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Bu email ile zaten hesap var.")

    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)

@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email veya sifre hatali.")

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)

# .env dosyasını yükle
load_dotenv()
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserInfo(BaseModel):
    id: int
    email: EmailStr


Base.metadata.create_all(bind=engine)

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
