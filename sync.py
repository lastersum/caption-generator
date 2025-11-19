import sqlite3
import requests

API_URL = "https://caption-generator-production-b824.up.railway.app/admin/users"
ADMIN_SECRET = "akilalmazmuratpususu61"  # .env'de ne koyduysan aynısı

# 1) Production'dan user listesi çek
res = requests.get(API_URL, headers={"x-admin-secret": ADMIN_SECRET})
res.raise_for_status()
users = res.json()

print(f"Production'dan {len(users)} kullanıcı geldi.")

# 2) Local caption.db'ye bağlan
conn = sqlite3.connect("caption.db")
cursor = conn.cursor()

# 3) İstersen önce tabloyu temizle (tam senkronizasyon için)
# Çok kritik: tablo adın gerçekten "users" mı, models.py ile aynı mı?
cursor.execute("DELETE FROM users")

# 4) Kullanıcıları tek tek ekle
for u in users:
    cursor.execute(
        """
        INSERT INTO users (id, email, plan)
        VALUES (?, ?, ?)
        """,
        (u["id"], u["email"], u.get("plan", "free")),
    )

conn.commit()
conn.close()

print("Senkronizasyon bitti, local caption.db güncellendi.")
