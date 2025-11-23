# services/first_love_model.py
import os, random, re, json, http.client, urllib.parse

ROMANTIC = {
    "0":"Destiny","1":"Unspoken Love","2":"Serendipity","3":"Shared Dreams","4":"Forever Promises",
    "5":"Cozy Moments","6":"Endless Laughter","7":"Warm Hugs","8":"Moonlight Walks","9":"Coffee Kisses"
}
COMPS = [
    "Your smile is my favorite sunrise 🌅",
    "Every day with you feels like a fairytale 🏰",
    "You're the poetry my soul always sought 💖",
    "You're the melody in my silence 🎶",
    "You're the only person who can steal my heart with a glance 💘",
    "When I see you, I forget how to breathe 🫶",
    "You're my once in a lifetime, never again 💫",
    "Even time slows down when you hold my hand ⏳",
    "You're not my type — you're my soulmate ❤️",
    "My heart beats in your rhythm 🌹",
    "Aha you found our secret!! ䷀䷀䷊䷂䷏䷓䷃䷀䷂䷏䷖䷔䷖䷗䷉䷕䷕䷗䷋䷒䷔䷊䷄䷔䷀䷏䷊䷐䷈䷑䷆䷘"
]
POEMS = [
    "Roses are red, violets are blue, every love story is beautiful, but ours is the truest of true 💕",
    "If love is a language, you're every word I've ever wanted to say 💌",
    "We are pages of a book, meant to be read hand in hand 📖",
    "My world began the moment you said 'I love you' 🌍",
    "You are the poem I never knew how to write, and this life is the story I always wanted to tell with you 📝",
    "In a sea of stars, your soul is my North 🌠",
    "Every second with you is a verse I never want to end ✍️",
    "We whispered under moons, but our hearts sang the loudest 💞",
    "Loving you is my favorite forever 🎀",
]

KEYMAP = [
    (re.compile(r"\b(forever|always|eternity)\b", re.I), "4"),
    (re.compile(r"\bmoon|night|stars?|perseids?\b", re.I), "8"),
    (re.compile(r"\bhug|hold|arms|cuddle\b", re.I), "7"),
    (re.compile(r"\bcoffee|latte|cappuccino\b", re.I), "9"),
    (re.compile(r"\bdestiny|fate\b", re.I), "0"),
    (re.compile(r"\bdream|future|plan\b", re.I), "3"),
    (re.compile(r"\bsmile|laugh|fun|joke\b", re.I), "6"),
    (re.compile(r"\bhome|cozy|warm\b", re.I), "5"),
    (re.compile(r"\bserendipity|chance|accident\b", re.I), "2"),
    (re.compile(r"\bunspoken|silent|unsaid\b", re.I), "1"),
]

# Toggle remote vs local with env:
REMOTE_URL = os.getenv("FIRST_LOVE_INFERENCE_URL")  # e.g. API Gateway URL for Lambda
BASE_ID    = os.getenv("FIRST_LOVE_BASE",   "distilbert-base-uncased")
ADAPTERID  = os.getenv("FIRST_LOVE_ADAPTER","first_love_you/deduction_classifier")
USE_HF     = os.getenv("FIRST_LOVE_USE_HF", "0") == "1"

def _heuristic(text: str):
    for rx, label in KEYMAP:
        if rx.search(text):
            return ROMANTIC[label], 0.92
    import random
    lab = random.choice(list(ROMANTIC.values()))
    return lab, round(random.uniform(0.6, 0.85), 2)

def _remote_infer(text: str):
    # Minimal HTTP client (stdlib) to avoid extra deps
    parsed = urllib.parse.urlparse(REMOTE_URL)
    body = json.dumps({"text": text}).encode()
    conn = http.client.HTTPSConnection(parsed.netloc) if parsed.scheme == "https" else http.client.HTTPConnection(parsed.netloc)
    path = parsed.path or "/"
    if parsed.query: path += "?" + parsed.query
    headers = {"Content-Type": "application/json"}
    conn.request("POST", path, body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    if resp.status != 200:
        raise RuntimeError(f"remote {resp.status}: {data[:200]}")
    obj = json.loads(data)
    return obj.get("theme"), float(obj.get("score", 0.8))

# AI model inference disabled to reduce dependencies
# def _hf_infer(text: str):
#     try:
#         import os
#         os.environ.setdefault("TOKENIZERS_PARALLELISM","false")
#         import torch; torch.set_num_threads(1)
#         from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
#         try:
#             from peft import PeftModel, PeftConfig
#             peft_cfg = PeftConfig.from_pretrained(ADAPTERID)
#             base_id = peft_cfg.base_model_name_or_path or BASE_ID
#         except Exception:
#             base_id = BASE_ID
#             PeftModel = None
#         base = AutoModelForSequenceClassification.from_pretrained(base_id, num_labels=10)
#         model = PeftModel.from_pretrained(base, ADAPTERID) if PeftModel else base
#         tok = AutoTokenizer.from_pretrained(base_id)
#         clf = pipeline("text-classification", model=model, tokenizer=tok, return_all_scores=False)
#         out = clf(text)[0]  # {'label':'LABEL_3','score':0.87}
#         import re
#         label = re.sub(r"^LABEL_","", out["label"])
#         return ROMANTIC.get(label, "Mystery"), float(out.get("score", 0.8))
#     except Exception:
#         return None, None

def _hf_infer(text: str):
    # Disabled: use heuristic fallback instead
    return None, None

def predict(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"error": "empty"}

    # 1) Remote Lambda?
    if REMOTE_URL:
        try:
            theme, score = _remote_infer(text)
            if theme:
                return {"theme": theme, "score": f"{score:.0%}", "engine": "lambda", "compliment": random.choice(COMPS), "poem": random.choice(POEMS)}
        except Exception:
            pass

    # 2) Local HF?
    if USE_HF:
        theme, score = _hf_infer(text)
        if theme:
            return {"theme": theme, "score": f"{score:.0%}", "engine": "hf+peft", "compliment": random.choice(COMPS), "poem": random.choice(POEMS)}

    # 3) Heuristic fallback (free!)
    theme, score = _heuristic(text)
    return {"theme": theme, "score": f"{score:.0%}", "engine": "heuristic", "compliment": random.choice(COMPS), "poem": random.choice(POEMS)}
