import re
from datetime import datetime, date
from typing import Optional, Dict, Any
from html.parser import HTMLParser
from app.core.parser import CATEGORY_RULES

INDO_MONTHS = {
    "januari": "January", "jan": "Jan",
    "februari": "February", "feb": "Feb",
    "maret": "March", "mar": "Mar",
    "april": "April", "apr": "Apr",
    "mei": "May",
    "juni": "June", "jun": "Jun",
    "juli": "July", "jul": "Jul",
    "agustus": "August", "agu": "Aug", "agt": "Aug",
    "september": "September", "sep": "Sep",
    "oktober": "October", "okt": "Oct",
    "november": "November", "nov": "Nov",
    "desember": "December", "des": "Dec"
}

class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.result.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "p", "tr", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("\n")

    def handle_endtag(self, tag):
        if tag in ("p", "tr", "div", "li", "table", "tbody", "thead"):
            self.result.append("\n")

    def get_text(self):
        return "\n".join(self.result)


def html_to_text(html_content: str) -> str:
    # 1. Strip style and script tags entirely
    cleaned = re.sub(r'(?is)<style[^>]*>.*?</style>', '', html_content)
    cleaned = re.sub(r'(?is)<script[^>]*>.*?</script>', '', cleaned)
    # 2. Extract visible text
    parser = HTMLTextExtractor()
    parser.feed(cleaned)
    raw = parser.get_text()
    # 3. Clean linebreaks
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    return "\n".join(lines)


def infer_category(merchant: str, description: str = "") -> str:
    """Infers Tillfold category from merchant and description text using CATEGORY_RULES."""
    combined = f"{merchant} {description}".lower()
    for cat_name, keywords in CATEGORY_RULES:
        for kw in keywords:
            if re.search(rf"\b{re.escape(kw.lower())}\b", combined):
                return cat_name
    return "Lainnya"


def _clean_amount_str(val_str: str) -> Optional[int]:
    """Parses Indonesian currency amount strings like 'Rp 10.000,00', '18.000', 'Rp1.300.332' into int."""
    if not val_str:
        return None
    cleaned = re.sub(r'(?i)^rp\.?\s*', '', val_str.strip())
    # Cut cents after comma if present (e.g. 10.000,00 -> 10.000)
    cleaned = cleaned.split(",")[0].strip()
    # Remove thousand separator dots
    cleaned = cleaned.replace(".", "")
    # Remove any non-digits
    digits = re.sub(r'\D', '', cleaned)
    if digits:
        try:
            return int(digits)
        except ValueError:
            pass
    return None


def _normalize_date_str(date_str: str) -> str:
    """Replaces Indonesian month names/abbreviations with English equivalents."""
    res = date_str
    for id_m, en_m in INDO_MONTHS.items():
        res = re.sub(rf"(?i)\b{id_m}\b", en_m, res)
    # Remove commas with spaces or standalone timezone strings
    res = re.sub(r'\s*,\s*', ' ', res)
    res = re.sub(r'(?i)\b(?:wib|ict|gmt\+7)\b', '', res).strip()
    return re.sub(r'\s+', ' ', res)


def _parse_datetime(raw_dt_str: str) -> Optional[datetime]:
    if not raw_dt_str:
        return None
    normalized = _normalize_date_str(raw_dt_str)
    formats = [
        "%d %B %Y %H:%M:%S",
        "%d %b %Y %H:%M:%S",
        "%d %B %Y %H:%M",
        "%d %b %Y %H:%M",
        "%d %B %Y",
        "%d %b %Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def parse_mandiri_receipt(html_content: str, raw_subject: str = "") -> Optional[Dict[str, Any]]:
    """
    Parses Bank Mandiri Livin' transaction receipt emails (noreply.livin@bankmandiri.co.id).
    Extracts: merchant, nominal, date, ref_number, source_account.
    """
    text = html_to_text(html_content)

    # Verification: must be Mandiri Livin
    if "bank mandiri" not in text.lower() and "livin" not in text.lower() and "mandiri" not in raw_subject.lower():
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 1. Extract Nominal / Amount
    nominal = None
    # Priority: Total Transaksi > Nominal Transaksi > Nominal Transfer > Nominal Top-up > Nominal
    for label in ["Total Transaksi", "Nominal Transaksi", "Nominal Transfer", "Nominal Top-up", "Nominal"]:
        match = re.search(rf"{label}\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
        if match:
            nominal = _clean_amount_str(match.group(1))
            if nominal:
                break

    if not nominal:
        # Check consecutive lines
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["total transaksi", "nominal transaksi", "nominal transfer", "nominal top-up"]):
                if i + 1 < len(lines):
                    parsed = _clean_amount_str(lines[i + 1])
                    if parsed:
                        nominal = parsed
                        break

    if not nominal:
        return None

    # 2. Extract Penerima / Merchant
    merchant = None
    for i, line in enumerate(lines):
        if line.lower() in ["penerima", "penyedia jasa", "tujuan", "nama penerima"]:
            if i + 1 < len(lines):
                val = lines[i + 1].strip()
                # If first line is masked account (e.g. aXXXXXX), look at line after
                if re.match(r'^[a-zA-Z0-9]{1,3}\*{4,}', val) and i + 2 < len(lines):
                    val = lines[i + 2].strip()
                merchant = val
                break

    if not merchant:
        penerima_match = re.search(r"(?:Penerima|Penyedia\s*Jasa|Tujuan)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
        if penerima_match:
            merchant = penerima_match.group(1).strip()

    # 3. Extract No. Referensi
    ref_number = None
    for label in ["No. Referensi BI Fast", "No. Referensi", "Nomor Referensi", "No Referensi", "No. Ref. QRIS"]:
        match = re.search(rf"{label}\s*[:\n]\s*([A-Za-z0-9]+)", text, re.IGNORECASE)
        if match:
            ref_number = match.group(1).strip()
            break

    if not ref_number:
        for i, line in enumerate(lines):
            if "referensi" in line.lower():
                if i + 1 < len(lines) and re.match(r'^[A-Za-z0-9]+$', lines[i + 1]):
                    ref_number = lines[i + 1].strip()
                    break

    # 4. Extract Tanggal & Jam
    tx_datetime = None
    date_val = None
    time_val = None

    for i, line in enumerate(lines):
        if line.lower() == "tanggal":
            if i + 1 < len(lines):
                date_val = lines[i + 1].strip()
        elif line.lower() == "jam":
            if i + 1 < len(lines):
                time_val = lines[i + 1].strip()

    if date_val:
        combined = f"{date_val} {time_val}" if time_val else date_val
        tx_datetime = _parse_datetime(combined)

    if not tx_datetime:
        date_match = re.search(r"Tanggal(?:\s*&\s*Jam)?\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
        if date_match:
            tx_datetime = _parse_datetime(date_match.group(1).strip())

    # 5. Extract Sumber Dana
    source_acc = None
    for i, line in enumerate(lines):
        if line.lower() in ["sumber dana", "rekening sumber"]:
            src_parts = []
            for j in range(i + 1, min(i + 3, len(lines))):
                if lines[j].lower() not in ["simpan email ini", "terima kasih", "informasi"]:
                    src_parts.append(lines[j])
            if src_parts:
                source_acc = " ".join(src_parts).strip()
            break

    cat = infer_category(merchant or "", text)
    ref_str = ref_number or ""
    merchant_clean = merchant or "Transaksi Mandiri"

    return {
        "bank": "mandiri",
        "nominal": nominal,
        "merchant": merchant_clean,
        "ref_number": ref_str,
        "datetime": tx_datetime,
        "source_account": source_acc or "Mandiri",
        "default_account": "Mandiri",
        "inferred_category": cat,
        "raw_text": f"Livin Mandiri: {merchant_clean} Rp {nominal:,} (Ref: {ref_str})"
    }


def parse_brimo_receipt(html_content: str, raw_subject: str = "") -> Optional[Dict[str, Any]]:
    """
    Parses Bank BRImo transaction receipt emails (BankBRI@bri.co.id).
    Extracts: merchant, nominal, date, ref_number, source_account.
    Determines account BRI 1 (Darurat) vs BRI 2 (Tabungan) based on tail digits:
    - ends in 1532 -> BRI 1 (Darurat)
    - ends in 6532 -> BRI 2 (Tabungan)
    - masked / ends in 532 -> BRI 1 (ambiguous, presents options)
    """
    text = html_to_text(html_content)

    if "bank rakyat indonesia" not in text.lower() and "brimo" not in text.lower() and "bri" not in raw_subject.lower():
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 1. Extract Nominal / Amount
    nominal = None
    for label in ["Total Transaksi", "Total", "Nominal", "Jumlah Transaksi"]:
        match = re.search(rf"{label}\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
        if match:
            nominal = _clean_amount_str(match.group(1))
            if nominal:
                break

    if not nominal:
        for i, line in enumerate(lines):
            if any(k == line.lower() for k in ["total transaksi", "total", "nominal", "jumlah transaksi"]):
                if i + 1 < len(lines):
                    parsed = _clean_amount_str(lines[i + 1])
                    if parsed:
                        nominal = parsed
                        break

    if not nominal:
        amount_match = re.search(r"Rp\.?\s*([\d\.,]+)", text)
        if amount_match:
            nominal = _clean_amount_str(amount_match.group(1))

    if not nominal:
        return None

    # 2. Extract Merchant / Tujuan / Penerima
    merchant = None
    for i, line in enumerate(lines):
        line_low = line.lower()
        if line_low in ["nama tujuan", "nama merchant"]:
            if i + 1 < len(lines):
                merchant = lines[i + 1].strip()
                break
        elif line_low in ["tujuan", "penerima", "merchant"]:
            if i + 1 < len(lines):
                val = lines[i + 1].strip()
                # In BRIVA emails, line i+1 might be masked code (e.g. aXXXXXXXX7) and line i+2 is the merchant (e.g. SHOPEE)
                if re.match(r'^[a-zA-Z0-9]{1,3}X{4,}', val) and i + 2 < len(lines):
                    val = lines[i + 2].strip()
                merchant = val
                break

    if not merchant:
        tujuan_match = re.search(r"(?:Nama\s*Tujuan|Nama\s*Merchant|Tujuan|Penerima|Merchant)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
        if tujuan_match:
            merchant = tujuan_match.group(1).strip()

    # 3. Extract No. Referensi
    ref_number = None
    for label in ["Nomor Referensi", "No. Referensi", "Ref Number", "No Referensi"]:
        match = re.search(rf"{label}\s*[:\n]\s*([A-Za-z0-9]+)", text, re.IGNORECASE)
        if match:
            ref_number = match.group(1).strip()
            break

    if not ref_number:
        for i, line in enumerate(lines):
            if "referensi" in line.lower():
                if i + 1 < len(lines) and re.match(r'^[A-Za-z0-9]+$', lines[i + 1]):
                    ref_number = lines[i + 1].strip()
                    break

    # 4. Extract Tanggal Transaksi
    tx_datetime = None
    for i, line in enumerate(lines):
        if line.lower() in ["tanggal transaksi", "tanggal", "waktu transaksi"]:
            if i + 1 < len(lines):
                tx_datetime = _parse_datetime(lines[i + 1].strip())
                if tx_datetime:
                    break

    if not tx_datetime:
        date_match = re.search(r"(?:Tanggal\s*Transaksi|Tanggal|Waktu\s*Transaksi)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
        if date_match:
            tx_datetime = _parse_datetime(date_match.group(1).strip())

    # 5. Extract Rekening Sumber Dana & Detect Account
    source_acc = None
    src_match = re.search(r"(?:Rekening\s*Sumber(?:\s*Dana)?|Sumber\s*Dana|Dari\s*Rekening)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
    if src_match and re.search(r'\d', src_match.group(1)):
        source_acc = src_match.group(1).strip()

    if not source_acc or not re.search(r'\d', source_acc):
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["rekening sumber dana", "sumber dana", "rekening sumber", "dari rekening"]):
                for j in range(i + 1, min(i + 4, len(lines))):
                    cand = lines[j].strip()
                    if cand.lower() in ["jenis transaksi", "catatan", "total", "nominal", "nama sumber dana"]:
                        continue
                    if re.search(r'\d', cand):
                        source_acc = cand
                        break
                    elif not source_acc:
                        source_acc = cand
                if source_acc and re.search(r'\d', source_acc):
                    break

    # Account determination according to Ground Truth:
    # BRI 1 (Darurat) ends in 1532
    # BRI 2 (Tabungan) ends in 6532
    # Masked (ends in 532): ambiguous, default to BRI 1 but allow interactive choice
    default_acc = "BRI 1"
    is_ambiguous = False
    if source_acc:
        clean_src = re.sub(r"\s+", "", source_acc)
        if clean_src.endswith("6532"):
            default_acc = "BRI 2"
        elif clean_src.endswith("1532"):
            default_acc = "BRI 1"
        elif clean_src.endswith("532"):
            is_ambiguous = True
            default_acc = "BRI 1"

    cat = infer_category(merchant or "", text)
    ref_str = ref_number or ""
    merchant_clean = merchant or "Transaksi BRImo"

    return {
        "bank": "bri",
        "nominal": nominal,
        "merchant": merchant_clean,
        "ref_number": ref_str,
        "datetime": tx_datetime,
        "source_account": source_acc or "BRI",
        "default_account": default_acc,
        "is_ambiguous_account": is_ambiguous,
        "inferred_category": cat,
        "raw_text": f"BRImo: {merchant_clean} Rp {nominal:,} (Ref: {ref_str})"
    }
