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

# ENV yerine şimdilik sabit key
SECRET_KEY = "CHANGE_THIS_SECRET_KEY_123456"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 gün

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

router = APIRouter()


# ------------------------------------------------------------
# Password helpers
# ------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ------------------------------------------------------------
# JWT helpers
# ------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


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
# AUTH DEPENDENCY → tam olarak api.py'nin beklediği fonksiyon
# ------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
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
    if not user:
        raise credentials_exception

    return user


# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------

from fastapi import APIRouter, Depends, HTTPException, status, Request
# ...

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

    # 2) device_id limiti (free hesaplar için)
    if user_in.device_id:
        existing_device = (
            db.query(User)
            .filter(
                User.device_id == user_in.device_id,
                User.plan == "free"   # sadece free hesapları kısıtla
            )
            .first()
        )
        if existing_device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu cihaz ile zaten bir ucretsiz hesap olusturulmus."
            )

    # (IP’yi de ek kontrol olarak istiyorsan burada bakabilirsin)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        client_ip = xff.split(",")[0].strip()
    else:
        client_ip = request.client.host

    # 3) Kullanıcıyı oluştur
    hashed_pw = get_password_hash(user_in.password)
    user = User(
        email=user_in.email,
        hashed_password=hashed_pw,
        plan="free",
        device_id=user_in.device_id,
        register_ip=client_ip,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form.username, form.password)

    if not user:
        raise HTTPException(status_code=400, detail="Yanlis email veya sifre.")

    token = create_access_token({"sub": user.email})
    return Token(access_token=token, token_type="bearer")


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user
