# set_pro.py
import sys
from sqlalchemy.orm import Session

from database import SessionLocal
from models import User


def set_user_plan(email: str, plan: str = "pro") -> None:
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"[X] Kullanici bulunamadi: {email}")
            return

        old_plan = user.plan
        user.plan = plan
        db.commit()
        db.refresh(user)

        print(f"[OK] {email} icin plan guncellendi: {old_plan} -> {user.plan}")
    finally:
        db.close()


def main():
    if len(sys.argv) < 2:
        print("Kullanim:")
        print("  python set_pro.py user@example.com            # PRO yap")
        print("  python set_pro.py user@example.com free       # FREE yap")
        sys.exit(1)

    email = sys.argv[1]
    plan = sys.argv[2] if len(sys.argv) >= 3 else "pro"
    set_user_plan(email, plan)


if __name__ == "__main__":
    main()
