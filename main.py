import os
from dotenv import load_dotenv
from openai import OpenAI
from prompts import SYSTEM_PROMPT

# .env içindeki ortam değişkenlerini yükle
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY .env dosyasında bulunamadı.")

# OpenAI istemcisi
client = OpenAI(api_key=api_key)


def generate_captions_and_hashtags(description: str, niche: str = "") -> str:
    """
    Verilen açıklama ve nişe göre 3 caption + 10 hashtag üretir.
    """
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


def main():
    print("📸 Caption & Hashtag Generator")
    print("-" * 40)

    niche = input("Niş (ör: YKS vlog, korku kesit, oyun, motivasyon): ").strip()

    print("\nVideo / post açıklamasını yaz.")
    print("Birden fazla satır yazabilirsin, bitince BOŞ SATIR bırakıp Enter'a bas:\n")

    lines = []
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)

    description = "\n".join(lines).strip()

    if not description:
        print("Açıklama girmedin, çıkıyorum.")
        return

    print("\n🧠 İçerik üretiliyor...\n")

    try:
        result = generate_captions_and_hashtags(description, niche)
        print(result)
        print("\n✅ Bitti, iyi kullan :)")
    except Exception as e:
        print("❌ Hata oluştu:")
        print(e)


if __name__ == "__main__":
    main()
