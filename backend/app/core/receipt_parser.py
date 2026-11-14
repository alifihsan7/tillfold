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
        if tag in ("br", "p", "tr", "div", "li", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6"):
            self.result.append("\n")

    def handle_endtag(self, tag):
        if tag in ("p", "tr", "div", "li", "td", "th", "table", "tbody", "thead"):
            self.result.append("\n")

    def get_text(self):
        return "\n".join(self.result)


def html_to_text(html_content: str) -> str:
    cleaned = re.sub(r'(?is)<style[^>]*>.*?</style>', '', html_content)
    cleaned = re.sub(r'(?is)<script[^>]*>.*?</script>', '', cleaned)
    parser = HTMLTextExtractor()
    parser.feed(cleaned)
    raw = parser.get_text()
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
    """Replaces Indonesian month names/abbreviations with English equivalents and cleans timezones."""
    res = date_str
    for id_m, en_m in INDO_MONTHS.items():
        res = re.sub(rf"(?i)\b{id_m}\b", en_m, res)
    # Remove commas
    res = re.sub(r'\s*,\s*', ' ', res)
    # Strip timezones like WIB, WITA, WIT, ICT, GMT+7, GMT+07:00, UTC+7, UTC, etc.
    res = re.sub(r'(?i)\b(?:wib|wita|wit|ict|gmt[+-]\d+(?::\d+)?|utc[+-]\d+(?::\d+)?|gmt|utc)\b', '', res).strip()
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
        "%d %B %Y %I:%M:%S %p",
        "%d %b %Y %I:%M:%S %p",
        "%d %B %Y %I:%M %p",
        "%d %b %Y %I:%M %p",
        "%B %d %Y %I:%M:%S %p",
        "%b %d %Y %I:%M:%S %p",
        "%B %d %Y %I:%M %p",
        "%b %d %Y %I:%M %p",
        "%B %d %Y %H:%M:%S",
        "%b %d %Y %H:%M:%S",
        "%B %d %Y %H:%M",
        "%b %d %Y %H:%M",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def resolve_internal_transfer(
    destination_name: Optional[str],
    destination_bank: Optional[str],
    destination_account_num: Optional[str],
    source_account: Optional[str] = None
) -> tuple[bool, Optional[str]]:
    """
    Determines if a transfer is internal (between user's own accounts)
    and resolves the destination account candidate.
    User's known name: Alif Ihsan.
    User's known accounts: Mandiri, BRI 1 (Darurat - ends in 1532), BRI 2 (Tabungan - ends in 6532), Bank Jago, Bibit.
    """
    name_clean = (destination_name or "").strip().lower()
    bank_clean = (destination_bank or "").strip().lower()
    acc_num_clean = re.sub(r"\D", "", destination_account_num or "")
    src_clean = (source_account or "").strip().lower()

    # If destination_name is present and clearly belongs to a 3rd party (does not contain "alif")
    # then this is NOT an internal transfer.
    if name_clean and "alif" not in name_clean:
        return False, None

    is_user_name = "alif" in name_clean
    is_known_bank = any(
        k in bank_clean for k in ["jago", "bibit", "bri", "mandiri", "livin", "bca", "seabank"]
    )

    if not (is_user_name or is_known_bank):
        return False, None

    candidate = None
    if "jago" in bank_clean:
        candidate = "Bank Jago"
    elif "bibit" in bank_clean:
        candidate = "Bibit"
    elif "mandiri" in bank_clean or "livin" in bank_clean:
        candidate = "Mandiri"
    elif "bri" in bank_clean:
        if acc_num_clean.endswith("6532"):
            candidate = "BRI 2"
        elif acc_num_clean.endswith("1532"):
            candidate = "BRI 1"
        elif "bri 1" in src_clean:
            candidate = "BRI 2"
        elif "bri 2" in src_clean:
            candidate = "BRI 1"
        else:
            candidate = "BRI 1"
    elif "bca" in bank_clean:
        candidate = "BCA"
    elif "seabank" in bank_clean:
        candidate = "SeaBank"
    elif is_user_name and not bank_clean:
        if "mandiri" in src_clean:
            candidate = "Bank Jago"
        elif "bri" in src_clean:
            candidate = "BRI 2" if "bri 1" in src_clean else "BRI 1"
        else:
            candidate = "Mandiri"

    return True, candidate


def parse_mandiri_receipt(html_content: str, raw_subject: str = "") -> Optional[Dict[str, Any]]:
    """
    Parses Bank Mandiri Livin' transaction receipt emails (noreply.livin@bankmandiri.co.id).
    Extracts: merchant, nominal, date, ref_number, source_account, transfer details.
    """
    text = html_to_text(html_content)

    # Verification: must be Mandiri Livin
    if "bank mandiri" not in text.lower() and "livin" not in text.lower() and "mandiri" not in raw_subject.lower():
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Detect whether transaction is a transfer
    is_transfer = any(
        k in text.lower() or k in raw_subject.lower()
        for k in [
            "transfer dengan bi fast",
            "transfer bi-fast",
            "transfer berhasil",
            "transfer online",
            "nominal transfer",
            "biaya transfer",
            "no. referensi bi fast",
            "nomor referensi bi fast",
            "pemindahan dana",
        ]
    )

    nominal = None
    admin_fee = 0

    if is_transfer:
        # Priority for transfer: Nominal Transfer > Nominal > Total Transaksi
        match = re.search(r"Nominal\s*Transfer\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
        if match:
            nominal = _clean_amount_str(match.group(1))

        if not nominal:
            for i, line in enumerate(lines):
                if "nominal transfer" in line.lower():
                    if i + 1 < len(lines):
                        parsed = _clean_amount_str(lines[i + 1])
                        if parsed:
                            nominal = parsed
                            break

        if not nominal:
            for label in ["Nominal", "Total Transaksi"]:
                match = re.search(rf"{label}\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
                if match:
                    nominal = _clean_amount_str(match.group(1))
                    if nominal:
                        break

        # Admin fee
        fee_match = re.search(r"(?:Biaya\s*(?:Transfer|Admin))\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
        if fee_match:
            admin_fee = _clean_amount_str(fee_match.group(1)) or 0
        else:
            for i, line in enumerate(lines):
                if any(k in line.lower() for k in ["biaya transfer", "biaya admin"]):
                    if i + 1 < len(lines):
                        parsed = _clean_amount_str(lines[i + 1])
                        if parsed is not None:
                            admin_fee = parsed
                            break
    else:
        for label in ["Total Transaksi", "Nominal Transaksi", "Nominal Transfer", "Nominal Top-up", "Nominal"]:
            match = re.search(rf"{label}\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
            if match:
                nominal = _clean_amount_str(match.group(1))
                if nominal:
                    break

        if not nominal:
            for i, line in enumerate(lines):
                if any(k in line.lower() for k in ["total transaksi", "nominal transaksi", "nominal transfer", "nominal top-up"]):
                    if i + 1 < len(lines):
                        parsed = _clean_amount_str(lines[i + 1])
                        if parsed:
                            nominal = parsed
                            break

    if not nominal:
        return None

    # Destination / Recipient / Merchant
    dest_name = None
    for i, line in enumerate(lines):
        if line.lower() in ["penerima", "penyedia jasa", "tujuan", "nama penerima"]:
            if i + 1 < len(lines):
                val = lines[i + 1].strip()
                if re.match(r'^[a-zA-Z0-9]{1,3}\*{4,}', val) and i + 2 < len(lines):
                    val = lines[i + 2].strip()
                dest_name = val
                break

    if not dest_name:
        penerima_match = re.search(r"(?:Penerima|Penyedia\s*Jasa|Tujuan|Nama\s*Penerima)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
        if penerima_match:
            dest_name = penerima_match.group(1).strip()

    # Destination Bank
    dest_bank = None
    bank_match = re.search(r"(?:Bank\s*Tujuan|Nama\s*Bank)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
    if bank_match:
        dest_bank = bank_match.group(1).strip()
    else:
        for i, line in enumerate(lines):
            if line.lower() in ["bank tujuan", "nama bank"]:
                if i + 1 < len(lines):
                    dest_bank = lines[i + 1].strip()
                    break

    if not dest_bank and is_transfer:
        for line in lines:
            ll = line.lower()
            if "bank mandiri" in ll or "livin" in ll:
                continue
            for b_kw in ["bank jago", "jago", "seabank", "bank bca", "bca", "bank bri", "bri", "bank bni", "bni", "bibit"]:
                if re.search(rf"\b{re.escape(b_kw)}\b", ll):
                    dest_bank = line.strip()
                    break
            if dest_bank:
                break

    # Destination Account Number
    dest_acc_num = None
    acc_match = re.search(r"(?:No\.?\s*(?:Rekening\s*)?Tujuan|Nomor\s*(?:Rekening\s*)?Tujuan|Rekening\s*Tujuan)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
    if acc_match:
        dest_acc_num = acc_match.group(1).strip()
    else:
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["no. rekening tujuan", "nomor rekening tujuan", "rekening tujuan"]):
                if i + 1 < len(lines):
                    dest_acc_num = lines[i + 1].strip()
                    break

    # No. Referensi
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

    # Tanggal & Jam
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

    # Sumber Dana
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

    is_internal = False
    dest_candidate = None
    if is_transfer:
        is_internal, dest_candidate = resolve_internal_transfer(
            destination_name=dest_name,
            destination_bank=dest_bank,
            destination_account_num=dest_acc_num,
            source_account="Mandiri"
        )

    ref_str = ref_number or ""
    merchant_clean = dest_name or ("Transfer Mandiri" if is_transfer else "Transaksi Mandiri")
    cat = "Transfer" if is_transfer else infer_category(merchant_clean, text)

    if is_transfer:
        target_display = dest_candidate or (f"{dest_name} ({dest_bank})" if dest_bank and dest_name != dest_bank else (dest_name or dest_bank or "Tujuan"))
        raw_text = f"Livin Mandiri: Transfer ke {target_display} Rp {nominal:,} (Ref: {ref_str})"
    else:
        raw_text = f"Livin Mandiri: {merchant_clean} Rp {nominal:,} (Ref: {ref_str})"

    return {
        "bank": "mandiri",
        "nominal": nominal,
        "merchant": merchant_clean,
        "ref_number": ref_str,
        "datetime": tx_datetime,
        "source_account": source_acc or "Mandiri",
        "default_account": "Mandiri",
        "inferred_category": cat,
        "raw_text": raw_text,
        "is_transfer": is_transfer,
        "is_internal_transfer": is_internal,
        "destination_bank": dest_bank,
        "destination_name": dest_name,
        "destination_account_num": dest_acc_num,
        "destination_account_candidate": dest_candidate,
        "admin_fee": admin_fee,
        "payment_method": None,
    }


def parse_brimo_receipt(html_content: str, raw_subject: str = "") -> Optional[Dict[str, Any]]:
    """
    Parses Bank BRImo transaction receipt emails (BankBRI@bri.co.id).
    Extracts: merchant, nominal, date, ref_number, source_account, transfer details.
    Determines account BRI 1 (Darurat) vs BRI 2 (Tabungan) based on tail digits:
    - ends in 1532 -> BRI 1 (Darurat)
    - ends in 6532 -> BRI 2 (Tabungan)
    - masked / ends in 532 -> BRI 1 (ambiguous, presents options)
    """
    text = html_to_text(html_content)
    text_low = text.lower()
    subject_low = raw_subject.lower()

    if (
        "bank rakyat indonesia" not in text_low
        and "bank bri" not in text_low
        and "brimo" not in text_low
        and "bri" not in subject_low
    ):
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Detect whether transaction is a transfer
    # QRIS payments are strictly non-transfer
    is_qris = "qris" in raw_subject.lower() or "pembelian qris" in text.lower() or "qr code" in text.lower()
    is_transfer = False
    if not is_qris:
        is_transfer = any(
            k in text.lower() or k in raw_subject.lower()
            for k in [
                "pemindahan dana",
                "transfer bank",
                "transfer bi-fast",
                "transfer bi fast",
                "transfer sesama",
                "transfer online",
                "nama tujuan",
                "bank tujuan",
                "nomor tujuan",
            ]
        )

    nominal = None
    admin_fee = 0

    if is_transfer:
        match = re.search(r"Nominal\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
        if match:
            nominal = _clean_amount_str(match.group(1))

        if not nominal:
            for i, line in enumerate(lines):
                if line.lower() == "nominal":
                    if i + 1 < len(lines):
                        parsed = _clean_amount_str(lines[i + 1])
                        if parsed:
                            nominal = parsed
                            break

        if not nominal:
            for label in ["Total Transaksi", "Total", "Jumlah Transaksi"]:
                match = re.search(rf"{label}\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
                if match:
                    nominal = _clean_amount_str(match.group(1))
                    if nominal:
                        break

        # Admin fee
        fee_match = re.search(r"(?:Biaya\s*(?:Admin|Transfer))\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
        if fee_match:
            admin_fee = _clean_amount_str(fee_match.group(1)) or 0
        else:
            for i, line in enumerate(lines):
                if any(k in line.lower() for k in ["biaya admin", "biaya transfer"]):
                    if i + 1 < len(lines):
                        parsed = _clean_amount_str(lines[i + 1])
                        if parsed is not None:
                            admin_fee = parsed
                            break
    else:
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

    # Destination / Merchant / Tujuan / Penerima
    dest_name = None
    for i, line in enumerate(lines):
        line_low = line.lower()
        if line_low in ["nama tujuan", "nama merchant"]:
            if i + 1 < len(lines):
                dest_name = lines[i + 1].strip()
                break
        elif line_low in ["tujuan", "penerima", "merchant"]:
            if i + 1 < len(lines):
                val = lines[i + 1].strip()
                if re.match(r'^[a-zA-Z0-9]{1,3}X{4,}', val) and i + 2 < len(lines):
                    val = lines[i + 2].strip()
                dest_name = val
                break

    if not dest_name:
        tujuan_match = re.search(r"(?:Nama\s*Tujuan|Nama\s*Merchant|Tujuan|Penerima|Merchant)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
        if tujuan_match:
            dest_name = tujuan_match.group(1).strip()

    # Destination Bank
    dest_bank = None
    bank_match = re.search(r"(?:Bank\s*Tujuan|Nama\s*Bank)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
    if bank_match:
        dest_bank = bank_match.group(1).strip()
    else:
        for i, line in enumerate(lines):
            if line.lower() in ["bank tujuan", "nama bank"]:
                if i + 1 < len(lines):
                    dest_bank = lines[i + 1].strip()
                    break

    if not dest_bank and ("sesama rekening bri" in text.lower() or "sesama rekening bri" in raw_subject.lower() or "sesama bri" in text.lower()):
        dest_bank = "BANK BRI"

    # Destination Account Number
    dest_acc_num = None
    acc_match = re.search(r"(?:Nomor\s*Tujuan|No\.?\s*Tujuan|Rekening\s*Tujuan|No\.?\s*Rekening\s*Tujuan)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
    if acc_match:
        dest_acc_num = acc_match.group(1).strip()
    else:
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["nomor tujuan", "no. tujuan", "rekening tujuan", "no. rekening tujuan"]):
                if i + 1 < len(lines):
                    dest_acc_num = lines[i + 1].strip()
                    break

    # No. Referensi
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

    # Tanggal Transaksi
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

    # Rekening Sumber Dana & Detect Account
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

    is_internal = False
    dest_candidate = None
    if is_transfer:
        is_internal, dest_candidate = resolve_internal_transfer(
            destination_name=dest_name,
            destination_bank=dest_bank,
            destination_account_num=dest_acc_num,
            source_account=default_acc
        )

    ref_str = ref_number or ""
    merchant_clean = dest_name or ("Transfer BRImo" if is_transfer else "Transaksi BRImo")
    cat = "Transfer" if is_transfer else infer_category(merchant_clean, text)

    if is_transfer:
        target_display = dest_candidate or (f"{dest_name} ({dest_bank})" if dest_bank and dest_name != dest_bank else (dest_name or dest_bank or "Tujuan"))
        raw_text = f"BRImo: Transfer ke {target_display} Rp {nominal:,} (Ref: {ref_str})"
    else:
        raw_text = f"BRImo: {merchant_clean} Rp {nominal:,} (Ref: {ref_str})"

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
        "raw_text": raw_text,
        "is_transfer": is_transfer,
        "is_internal_transfer": is_internal,
        "destination_bank": dest_bank,
        "destination_name": dest_name,
        "destination_account_num": dest_acc_num,
        "destination_account_candidate": dest_candidate,
        "admin_fee": admin_fee,
        "payment_method": None,
    }


def parse_google_play_receipt(html_or_text: str, raw_subject: str = "") -> Optional[Dict[str, Any]]:
    """
    Parses Google Play order receipts (googleplay-noreply@google.com).
    Extracts: ref_number (GPA.XXXX-XXXX-XXXX-XXXXX), nominal (total amount),
    merchant/item, datetime, payment_method, category, default_account.
    """
    if "<" in html_or_text and ">" in html_or_text:
        text = html_to_text(html_or_text)
    else:
        text = html_or_text.strip()

    valid_source = (
        "googleplay-noreply@google.com" in raw_subject.lower()
        or "google play" in raw_subject.lower()
        or "google play" in text.lower()
    )
    has_order_marker = (
        "order number" in text.lower()
        or "nomor pesanan" in text.lower()
        or "gpa." in text.lower()
    )
    if not (valid_source and has_order_marker):
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # 1. Order Number / Ref Number
    ref_match = re.search(r"\b(GPA\.[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4,5})\b", text)
    if not ref_match:
        ref_match = re.search(r"\b(GPA\.[0-9\-]+)\b", text)
    if not ref_match:
        return None
    ref_number = ref_match.group(1).strip()

    # 2. Nominal (Total including tax)
    nominal = None
    match = re.search(r"Total\s*[:\n]\s*(?:Rp\.?\s*)?([\d\.,]+)", text, re.IGNORECASE)
    if match:
        nominal = _clean_amount_str(match.group(1))

    if not nominal:
        for i, line in enumerate(lines):
            if line.lower() == "total" or line.lower().startswith("total:"):
                cand = line.split(":", 1)[1] if ":" in line else (lines[i + 1] if i + 1 < len(lines) else "")
                parsed = _clean_amount_str(cand)
                if parsed:
                    nominal = parsed
                    break

    if not nominal:
        all_amounts = re.findall(r"Rp\.?\s*([\d\.,]+)", text, re.IGNORECASE)
        valid_amounts = [a for a in (_clean_amount_str(x) for x in all_amounts) if a is not None]
        if valid_amounts:
            nominal = max(valid_amounts)

    if not nominal:
        return None

    # 3. Item / Merchant
    item = None
    item_match = re.search(r"(?:Item|Barang|Deskripsi|Description)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
    if item_match:
        cand = item_match.group(1).strip()
        if cand.lower() not in ["price", "harga", "total", "subtotal"]:
            item = cand

    if not item:
        for i, line in enumerate(lines):
            if line.lower() in ["item", "barang", "deskripsi", "description"]:
                for j in range(i + 1, min(i + 5, len(lines))):
                    cand = lines[j].strip()
                    if cand.lower() in ["price", "harga", "total", "subtotal"]:
                        continue
                    if re.match(r"^(?:rp\.?\s*)?[\d\.,]+", cand.lower()):
                        continue
                    item = cand
                    break
                if item:
                    break

    if not item:
        item = "Google Play Purchase"

    # 4. Payment Method
    payment_method = None
    pm_match = re.search(r"(?:Payment\s*method|Metode\s*pembayaran)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
    if pm_match:
        payment_method = pm_match.group(1).strip()
    else:
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["payment method", "metode pembayaran"]):
                if i + 1 < len(lines):
                    payment_method = lines[i + 1].strip()
                    break
    if not payment_method:
        payment_method = "Google Play"

    # 5. Datetime
    tx_datetime = None
    dt_match = re.search(r"(?:Order\s*date|Tanggal\s*(?:pemesanan|pesanan)|Tanggal)\s*[:\n]\s*([^\n\r]+)", text, re.IGNORECASE)
    if dt_match:
        tx_datetime = _parse_datetime(dt_match.group(1).strip())
    if not tx_datetime:
        for i, line in enumerate(lines):
            if any(k in line.lower() for k in ["order date", "tanggal pemesanan", "tanggal pesanan"]):
                if ":" in line:
                    cand = line.split(":", 1)[1].strip()
                    tx_datetime = _parse_datetime(cand)
                    if tx_datetime:
                        break
                if i + 1 < len(lines):
                    tx_datetime = _parse_datetime(lines[i + 1].strip())
                    if tx_datetime:
                        break

    # 6. Inferred Category & Account
    cat = infer_category(item, text)
    if cat == "Lainnya":
        cat = "Langganan & Servis"

    default_acc = "BRI 1"

    return {
        "bank": "google_play",
        "nominal": nominal,
        "merchant": item,
        "ref_number": ref_number,
        "datetime": tx_datetime,
        "source_account": default_acc,
        "default_account": default_acc,
        "inferred_category": cat,
        "raw_text": f"Google Play: {item} Rp {nominal:,} (Order {ref_number})",
        "is_transfer": False,
        "is_internal_transfer": False,
        "destination_bank": None,
        "destination_name": None,
        "destination_account_num": None,
        "destination_account_candidate": None,
        "admin_fee": 0,
        "payment_method": payment_method,
    }
