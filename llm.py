import json
import os

from openai import OpenAI

CATEGORIES = ["SIMRS Error", "Jaringan/Koneksi", "Hardware", "Akun/Password", "Lainnya"]
PRIORITIES = ["Rendah", "Sedang", "Tinggi"]

_client = None


def _get_client() -> OpenAI:
    # Groq's API is OpenAI-compatible and free to use, so the openai SDK works unchanged.
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url="https://api.groq.com/openai/v1")
    return _client


PROMPT = """Kamu adalah asisten yang mengubah laporan bebas dari pengguna SIMRS menjadi tiket IT Support terstruktur.

Kategori yang valid: {categories}
Prioritas yang valid: {priorities}

Balas HANYA dengan JSON, tanpa teks lain, dengan format:
{{"category": "...", "priority": "...", "description": "ringkasan singkat dan jelas"}}

Laporan pengguna: "{message}\""""


def parse_extraction(raw_text: str) -> dict:
    """Parse the model's JSON reply, falling back to safe defaults if malformed."""
    try:
        data = json.loads(raw_text)
        category = data.get("category", "Lainnya")
        priority = data.get("priority", "Sedang")
        description = data.get("description", raw_text)
    except (json.JSONDecodeError, AttributeError):
        category, priority, description = "Lainnya", "Sedang", raw_text

    if category not in CATEGORIES:
        category = "Lainnya"
    if priority not in PRIORITIES:
        priority = "Sedang"
    return {"category": category, "priority": priority, "description": description}


def extract_ticket(message: str, requester_name: str) -> dict:
    prompt = PROMPT.format(
        categories=", ".join(CATEGORIES),
        priorities=", ".join(PRIORITIES),
        message=message,
    )
    response = _get_client().chat.completions.create(
        model="openai/gpt-oss-20b",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    ticket = parse_extraction(response.choices[0].message.content)
    ticket["requester_name"] = requester_name
    return ticket
