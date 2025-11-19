# models.py
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # plan: "free" veya "pro"
    plan = Column(String, nullable=False, default="free")
    device_id = Column(String, nullable=True, index=True)
    register_ip = Column(String, nullable=True, index=True)  # İstersen IP de kalsın
    # Iliski
    usages = relationship("CaptionUsage", back_populates="user")


class CaptionUsage(Base):
    __tablename__ = "caption_usages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    count = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="usages")
