import base64
import json
import os
import requests
from typing import List, Dict, Any, Optional

from app.core.config import settings

def get_ai_api_key() -> str:
    key = settings.AI_ROUTER_KEY or os.getenv("AI_ROUTER_KEY", "")
    if not key:
        # Fallback to hermes .env
        hermes_env = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(hermes_env):
            with open(hermes_env, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("HERMES_CUSTOM_LOCALHOST_20128_API_KEY="):
                        key = line.strip().split("=", 1)[1]
                        break
    return key

def clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end+1]
    return text

def extract_from_media(
    media_bytes: bytes,
    mime_type: str,
    media_type: str = "image",  # "image" or "audio"
    caption: str = "",
    accounts: Optional[List[str]] = None
) -> Dict[str, Any]:
    api_key = get_ai_api_key()
    if not api_key:
        return {
            "success": False,
            "error": "API Key AI Router tidak ditemukan di sistem."
        }

    valid_accounts = accounts or []
    if not valid_accounts:
        return {"success": False, "error": "Tambahkan rekening di web sebelum memproses media."}
    acc_list_str = ", ".join(valid_accounts)

    system_prompt = f"""Kamu adalah mesin ekstraksi Tillfold untuk membaca struk belanja, screenshot mutasi/QRIS (Livin Mandiri, GoPay, BCA, dll.), dan rekaman suara (voice note).

Rekening yang terdaftar di sistem:
{acc_list_str}
Gunakan hanya nama rekening terdaftar. Jika rekening tidak disebut, isi account dengan null agar sistem memakai rekening default pengguna. Untuk transfer, asal dan tujuan wajib disebut dan berbeda.

Kategori pengeluaran yang didukung:
- Makanan & Minuman (makan nasi, warteg, resto, grabfood, gofood)
- Jajan / Ngopi (kopi, boba, snack, indomaret/alfamart jajan)
- Laundry (cuci pakaian, cuci sepatu)
- Galon & Air (isi ulang air mineral galon, le minerale, aqua)
- Langganan (Spotify, YouTube, Netflix, Cloud, Gym Membership)
- Tagihan (Listrik PLN, Wifi indihome, Pulsa seluler)
- Transportasi (Bensin pertamina, ojol grab/gojek, tol, parkir)
- Kesehatan (Obat, apotek, suplemen, dokter)
- Belanja (Pakaian, perlengkapan pribadi, elektronik)
- Hiburan (Bioskop XXI, game steam)
- Lain-lain

Pemasukan: kategori 'Gajian' atau 'Pemasukan Lain'.

Aturan Ekstraksi:
1. Analisis konten dengan teliti. Jika ini struk/QRIS, cari TOTAL AKHIR/TOTAL BAYAR (bukan subtotal atau kembalian).
2. Jika ada nama merchant/toko (misal 'Indomaret', 'Kopi Kenangan', 'Warteg Sedap'), jadikan keterangan.
3. Jika audio/voice note, dengarkan ucapan user dengan akurat (bahasa Indonesia/campuran), tangkap nominal, barang/aktivitas, dan rekening jika disebut.
4. Jika user menyebut transfer (misal "transfer dari mandiri ke bibit 500rb"), set type: 'transfer' dengan from_account dan to_account.
5. Format pengembalian WAJIB JSON murni sesuai schema berikut:
{{
  "detected": true,
  "kind": "receipt" | "qris" | "transfer_receipt" | "voice_note" | "other",
  "transcription": "transkripsi ucapan suara atau ringkasan teks struk yang terbaca",
  "transactions": [
    {{
      "type": "expense" | "income" | "transfer",
      "amount": 25000,
      "account": null,
      "category": "Makanan & Minuman",
      "description": "Warteg Makan Siang",
      "from_account": "nama rekening asal terdaftar", // jika transfer
      "to_account": "nama rekening tujuan terdaftar"      // jika transfer
    }}
  ]
}}
Jika tidak ada transaksi keuangan yang valid/terdeteksi, kembalikan:
{{
  "detected": false,
  "transcription": "keterangan mengapa tidak terdeteksi",
  "transactions": []
}}"""

    b64_data = base64.b64encode(media_bytes).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{b64_data}"

    user_content = []
    if caption:
        user_content.append({
            "type": "text",
            "text": f"Pesan / Catatan tambahan dari user: \"{caption}\"\nHarap pertimbangkan catatan ini saat menentukan kategori, keterangan, atau rekening."
        })
    else:
        user_content.append({
            "type": "text",
            "text": "Harap ekstrak data transaksi keuangan dari media terlampir secara presisi."
        })

    user_content.append({
        "type": "image_url",
        "image_url": {
            "url": data_uri
        }
    })

    payload = {
        "model": settings.AI_ROUTER_MODEL,
        "stream": False,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1
    }

    try:
        url = f"{settings.AI_ROUTER_URL.rstrip('/')}/chat/completions"
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=45
        )
        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"AI Router error ({resp.status_code}): {resp.text}"
            }

        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        cleaned = clean_json_text(raw_text)
        result_json = json.loads(cleaned)
        result_json["success"] = True
        return result_json
    except Exception as e:
        return {
            "success": False,
            "error": f"Gagal mengekstrak media: {str(e)}"
        }
