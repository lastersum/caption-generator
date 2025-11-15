FROM python:3.11-slim

# Çalışma klasörü
WORKDIR /app

# Gereksinimleri kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tüm projeyi kopyala
COPY . .

# Varsayılan başlatma komutu
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
