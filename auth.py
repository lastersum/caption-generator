# auth.py
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User
from schemas import UserCreate, Token, UserPublic

# ------------------------------------------------------------
# Sabit JWT ayarları (istenirse .env'e taşınabilir)
# ------------------------------------------------------------
SECRET_KEY = "CHANGE_THIS_SECRET_KEY_123456"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 gün

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Swagger / docs için tokenUrl -> /auth/login
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter()


# ------------------------------------------------------------
# Password helpers
# ------------------------------------------------------------
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ------------------------------------------------------------
# JWT helpers
# ------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# ------------------------------------------------------------
# DB helpers
# ------------------------------------------------------------
def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


# ------------------------------------------------------------
# AUTH dependency -> api.py burayı kullanıyor
# ------------------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Gecersiz kimlik bilgileri.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_email(db, email=email)
    if user is None:
        raise credentials_exception

    return user


# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------

@router.post("/register", response_model=UserPublic)
def register(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    # 1) Email zaten var mı?
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu email ile kayitli kullanici zaten var.",
        )

    # 2) device_id limiti (free hesaplar icin)
    device_id = getattr(user_in, "device_id", None)
    if device_id:
        existing_device = (
            db.query(User)
            .filter(
                User.device_id == device_id,
                User.plan == "free",  # sadece free hesapları kısıtla
            )
            .first()
        )
        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu cihaz ile zaten bir ucretsiz hesap olusturulmus.",
            )

    # 3) IP'yi al (Railway behind proxy -> x-forwarded-for)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        client_ip = xff.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else None

    # 4) Kullanıcıyı oluştur
    hashed_pw = get_password_hash(user_in.password)

    user = User(
        email=user_in.email,
        hashed_password=hashed_pw,
        plan="free",
        device_id=device_id,
        register_ip=client_ip,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # form_data.username -> email
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yanlis email veya sifre.",
        )

    access_token = create_access_token(data={"sub": user.email})
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserPublic)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user
