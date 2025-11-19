import sqlite3
import requests

API_URL = "https://caption-generator-production-b824.up.railway.app/admin/users"
ADMIN_SECRET = "akilalmazmuratpususu61"

# Production Users çek
res = requests.get(API_URL, headers={"x-admin-secret": ADMIN_SECRET})
users = res.json()

# Local DB aç
conn = sqlite3.connect("caption.db")
cursor = conn.cursor()

# Gerekliyse tabloyu sıfırla
cursor.execute("DELETE FROM users")

# Kullanıcıları ekle
for u in users:
    cursor.execute("""
        INSERT INTO users (id, email, plan, created_at)
        VALUES (?, ?, ?, ?)
    """, (u["id"], u["email"], u["plan"], u["created_at"]))

conn.commit()
conn.close()

print("Senkronizasyon tamamlandı.")
