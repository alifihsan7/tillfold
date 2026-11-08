from typing import Optional
import re


def extract_spreadsheet_id(url_or_id: Optional[str]) -> str:
    """Mengekstrak Spreadsheet ID murni dari link URL Google Sheets apa pun atau mengembalikan string mentah jika sudah berupa ID."""
    if not url_or_id:
        return ""
    text = url_or_id.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        return match.group(1)
    match_d = re.search(r"^d/([a-zA-Z0-9-_]+)", text)
    if match_d:
        return match_d.group(1)
    clean = text.split("?")[0].split("#")[0].strip("/")
    return clean
