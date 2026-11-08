import re

# Specific regex patterns for account detection (multi-word patterns first)
ACCOUNT_PATTERNS = [
    (r"\b(?:bank\s*bri[\s-]*1|bri[\s-]*1|bri1)\b", "BRI 1"),
    (r"\b(?:bank\s*bri[\s-]*2|bri[\s-]*2|bri2)\b", "BRI 2"),
    (r"\b(?:bank\s*bri|bri)\b", "BRI 1"),
    (r"\b(?:bank\s*mandiri|mandiri|livin)\b", "Mandiri"),
    (r"\b(?:bank\s*jago|jago)\b", "Bank Jago"),
    (r"\b(?:bibit)\b", "Bibit"),
    (r"\b(?:bank\s*bca|bca|halo\s*bca)\b", "BCA"),
    (r"\b(?:bank\s*bni|bni)\b", "BNI"),
    (r"\b(?:seabank)\b", "SeaBank"),
    (r"\b(?:gopay|go-pay)\b", "GoPay"),
    (r"\b(?:ovo)\b", "OVO"),
    (r"\b(?:dana)\b", "DANA"),
    (r"\b(?:shopeepay|spay)\b", "ShopeePay"),
    (r"\b(?:cash|tunai|dompet)\b", "Cash"),
]

INCOME_KEYWORDS = [
    "gaji", "income", "pemasukan", "terima", "dapat", "transfer masuk", 
    "transferan", "freelance", "bonus", "cashback", "dividen", "angpao", "cuan", "uang saku"
]

# Order matters: more specific envelopes first!
CATEGORY_RULES = [
    ("Makanan & Minuman", [
        "nasgor", "nasi goreng", "miegor", "mie goreng", "mie", "bakmi", "kwetiau", 
        "bihun", "bubur", "pecel", "lele", "soto", "nasi", "ayam", "bebek", "sate", 
        "bakso", "rawon", "gudeg", "warteg", "padang", "geprek", "rendang", "resto", 
        "makan", "minum", "lunch", "dinner", "sarapan", "breakfast", "kantin", "warung",
        "burger", "pizza", "mcd", "kfc"
    ]),
    ("Jajan / Ngopi", [
        "warkop", "kopi", "coffee", "cafe", "kafe", "starbucks", "kenangan", "janji jiwa", 
        "tomoro", "fore", "boba", "chatime", "es teh", "esteh", "teh", "mixue", "snack", 
        "cemilan", "roti", "ice cream", "eskrim", "croissant", "jajan", "gorengan",
        "martabak", "cilok", "cireng", "siomay", "batagor", "tahu bulat"
    ]),
    ("Laundry", [
        "laundry", "cuci baju", "cuci pakaian", "londri", "setrika", "dry clean"
    ]),
    ("Galon & Air", [
        "galon", "isi ulang", "aqua galon", "cleo galon", "le minerale galon", "air minum"
    ]),
    ("Langganan & Servis", [
        "netflix", "spotify", "youtube premium", "yt premium", "icloud", "chatgpt", 
        "github copilot", "subscription", "langganan", "wifi", "indihome", "biznet", 
        "myrepublic", "firstmedia", "listrik", "pln", "token", "pulsa", "kuota", 
        "paket data", "telkomsel", "byu", "xl", "indosat", "kos", "kost", "kontrakan"
    ]),
    ("Investasi & Tabungan", [
        "bibit", "reksadana", "saham", "crypto", "nabung", "invest", "deposito"
    ]),
    ("Transportasi", [
        "bensin", "pertalite", "pertamax", "shell", "solar", "gojek", "goride", 
        "gocar", "grab", "grabcar", "grabike", "maxim", "parkir", "tol", "kereta", 
        "krl", "mrt", "lrt", "busway", "transjakarta", "ojol", "angkot", "service motor", 
        "cuci motor", "cuci mobil"
    ]),
    ("Kebutuhan Harian", [
        "indomaret", "alfamart", "supermarket", "hypermart", "belanja", "sabun", 
        "odol", "shampoo", "beras", "baju", "celana", "sepatu", "tokped", "tokopedia", 
        "shopee", "lazada", "tiktok shop", "skincare", "tisu", "deterjen"
    ]),
    ("Kesehatan & Gym", [
        "gym", "fitness", "membership", "suplemen", "whey", "creatine", "obat", 
        "vitamin", "apotek", "dokter", "klinik", "panadol", "paracetamol"
    ]),
    ("Hiburan", [
        "nonton", "bioskop", "cinema", "xxi", "cgv", "game", "steam", "topup", 
        "playstation", "wisata", "liburan", "karaoke"
    ])
]

# Intelligent fallback account based on category when no account is explicitly typed
CATEGORY_DEFAULT_ACCOUNT = {
    "Langganan & Servis": "Bank Jago",
    "Investasi & Tabungan": "Bibit",
}

def parse_amount_with_span(text: str) -> tuple[int | None, str | None, tuple[int, int] | None]:
    pattern = r'(?i)(?<!\w)((?:rp|idr)\.?\s*)?(\d+(?:[.,]\d+)*|[.,]\d+)\s*(k|rb|ribu|jt|juta|m|mio)?\b'
    matches = list(re.finditer(pattern, text))
    if not matches:
        return None, None, None

    candidates = []
    for idx, match in enumerate(matches):
        prefix = match.group(1)
        num_str = match.group(2)
        unit = (match.group(3) or '').lower()

        if unit:
            num_clean = num_str.replace(',', '.')
            try:
                val = float(num_clean)
            except ValueError:
                continue

            if unit in ['k', 'rb', 'ribu']:
                multiplier = 1_000
            elif unit in ['jt', 'juta', 'm', 'mio']:
                multiplier = 1_000_000
            else:
                multiplier = 1
            amount = int(val * multiplier)
            if amount > 0:
                # Explicit unit suffix has highest priority (3)
                candidates.append((3, idx, amount, match.group(0), match.span()))
        else:
            # Standalone leading dot/comma without unit is not a valid rupiah nominal
            if num_str.startswith(('.', ',')):
                continue
            cleaned = num_str.replace('.', '').replace(',', '')
            if cleaned.isdigit() and int(cleaned) > 0:
                amount = int(cleaned)
                if prefix:
                    # Explicit currency prefix (e.g. rp 25000, rp. 25.000) has highest priority (3)
                    prio = 3
                elif len(cleaned) == 1:
                    # Standalone single digit (e.g. 1, 2) has lowest priority (1)
                    prio = 1
                else:
                    # Multi-digit without unit/prefix (e.g. 25000, 25.000.000) has medium priority (2)
                    prio = 2
                candidates.append((prio, idx, amount, match.group(0), match.span()))

    if not candidates:
        return None, None, None

    # Sort candidates: highest priority score descending, then text appearance order ascending
    candidates.sort(key=lambda c: (-c[0], c[1]))
    best = candidates[0]
    return best[2], best[3], best[4]

def parse_amount(text: str) -> tuple[int | None, str | None]:
    amt, matched, _ = parse_amount_with_span(text)
    return amt, matched

def split_raw_into_items(text: str) -> list[str]:
    clean = text.strip()
    if not clean:
        return []

    # Priority 1: Multi-line message
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    if len(lines) > 1:
        return lines

    # Priority 2: Comma or semicolon separated (do not split commas flanked by digits)
    if "," in clean or ";" in clean:
        parts = [p.strip() for p in re.split(r';+|(?:(?<!\d),|,(?!\d))+', clean) if p.strip()]
        if len(parts) > 1:
            return parts

    # Priority 3: Multiple amounts in single line (e.g. 'nasgor 20k kopi 28k')
    amt_pattern = (
        r'(?i)(?<!\w)(?:(?:rp|idr)\.?\s*)?(?:\d+(?:[.,]\d+)*|[.,]\d+)\s*(?:k|rb|ribu|jt|juta|m|mio)\b|'
        r'(?<!\w)(?:rp|idr)\.?\s*(?:\d+(?:[.,]\d+)*)\b'
    )
    matches = list(re.finditer(amt_pattern, clean, flags=re.IGNORECASE))
    
    if len(matches) <= 1:
        return [clean]

    segments = []
    last_end = 0
    for i, m in enumerate(matches):
        seg = clean[last_end:m.end()].strip()
        seg = re.sub(r'^(?:dan|\+|&)\s*', '', seg, flags=re.IGNORECASE)
        segments.append(seg)
        last_end = m.end()

    if last_end < len(clean):
        trailing = clean[last_end:].strip()
        if trailing and segments:
            segments[-1] += " " + trailing

    return segments

def parse_transaction(text: str):
    raw = text.strip()
    if not raw:
        return {"success": False, "error": "Pesan kosong"}

    # 1. Detect and extract explicit account first to protect account numbers (e.g. BRI 1, BRI 2)
    selected_account = None
    remaining = raw
    for pattern, acc_name in ACCOUNT_PATTERNS:
        matches = list(re.finditer(pattern, remaining, re.IGNORECASE))
        valid_match = None
        for m in matches:
            # Disambiguate account keywords that clash with item descriptions
            if acc_name == "Bank Jago" and m.group(0).lower() == "jago":
                prefix_text = remaining[:m.start()].rstrip().lower()
                if prefix_text.endswith(("ayam", "ikan", "bebek")):
                    continue
            if acc_name == "Bibit":
                suffix_text = remaining[m.end():].lstrip().lower()
                crop_words = (
                    "cabe", "cabai", "tomat", "tanaman", "pohon", "bunga", "buah",
                    "sayur", "sayuran", "lele", "ikan", "jagung", "padi", "kangkung",
                    "bayam", "sawit", "unggul", "jamur", "benih", "pupuk"
                )
                if any(suffix_text.startswith(w) for w in crop_words):
                    continue
            if acc_name == "DANA":
                suffix_text = remaining[m.end():].lstrip().lower()
                if suffix_text.startswith("darurat"):
                    continue

            valid_match = m
            break

        if valid_match:
            selected_account = acc_name
            remaining = remaining[:valid_match.start()] + " " + remaining[valid_match.end():]
            break

    # 2. Extract transaction amount with unit priority
    amount, matched_num, span = parse_amount_with_span(remaining)
    if not amount or not matched_num or not span:
        return {
            "success": False, 
            "error": "Nominal tidak terdeteksi. Contoh format: `nasi padang 25k` atau `kopi 20k mandiri`"
        }

    # Remove matched amount from remaining text via exact span
    remaining = remaining[:span[0]] + " " + remaining[span[1]:]

    # 3. Check transaction type (income vs expense)
    is_income = False
    for ikw in INCOME_KEYWORDS:
        if re.search(rf'\b{re.escape(ikw)}\b', raw.lower()):
            is_income = True
            break

    tx_type = "income" if is_income else "expense"

    # 4. Determine category
    selected_category = "Pemasukan" if is_income else "Lainnya"
    if not is_income:
        for cat_name, cat_kws in CATEGORY_RULES:
            matched = False
            for ckw in cat_kws:
                if ckw == "bibit":
                    # Do not classify agricultural seeds as financial investment
                    if re.search(r'\bbibit\b(?!\s+(?:cabe|cabai|tomat|tanaman|pohon|bunga|buah|sayur|sayuran|lele|ikan|jagung|padi|kangkung|bayam|sawit|unggul|jamur|benih|pupuk))', raw.lower()):
                        selected_category = cat_name
                        matched = True
                        break
                else:
                    if re.search(rf'\b{re.escape(ckw)}\b', raw.lower()):
                        selected_category = cat_name
                        matched = True
                        break
            if matched:
                break

    account_explicit = selected_account is not None

    # 5. Smart-infer fallback account if no explicit account was given
    if not selected_account:
        if selected_category in CATEGORY_DEFAULT_ACCOUNT:
            selected_account = CATEGORY_DEFAULT_ACCOUNT[selected_category]
        elif is_income:
            selected_account = "BRI 1"  # Default hub for income
        else:
            selected_account = "Mandiri"  # Default daily operational pocket

    # 6. Description cleanup
    desc_clean = re.sub(r'[^\w\s-]', '', remaining).strip()
    desc_clean = re.sub(r'\s+', ' ', desc_clean)

    if not desc_clean:
        desc_clean = selected_category
    else:
        desc_clean = desc_clean.capitalize()

    return {
        "success": True,
        "type": tx_type,
        "amount": amount,
        "account": selected_account,
        "account_explicit": account_explicit,
        "category": selected_category,
        "description": desc_clean,
        "raw_text": raw
    }

def parse_multi_transactions(text: str) -> list[dict]:
    items = split_raw_into_items(text)
    results = []
    for item in items:
        parsed = parse_transaction(item)
        if parsed.get("success"):
            results.append(parsed)
    return results
