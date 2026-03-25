from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
import markdown

router = APIRouter()
templates = Jinja2Templates(directory="apps/api/templates")

# Christmas treasure hunt riddles with locations
# Each location gives a word clue that forms a final riddle
# Final riddle: "Every moment with you is" → Answer: "LOVE"
RIDDLES = [
    {
        "id": 1,
        "riddle_cn": "我见证你的笑容，也映照你的思绪，\n光影流转的故事里，藏着我们的回忆。\n当银幕暗下，星光熄灭那一瞬，\n请向我背后探寻，那里有爱的低语。",
        "riddle_en": "I witness your smiles and reflect your deepest thoughts,\nIn flickering tales of light, our memories are caught.\nWhen the screen fades to darkness, and all the stars retreat,\nLook behind my silent frame—there love and secrets meet.",
        "hint": "每个温暖的夜晚，我们依偎在它面前...",
        "location": "电视机后面",
        "location_en": "Behind the TV",
        "secret_word": "not alive",
        "word_hint_cn": "你会在那里找到第一个词",
        "word_hint_en": "You'll find the first word there"
    },
    {
        "id": 2,
        "riddle_cn": "我栖息在云端，守护着温馨的味道，\n锅碗奏响的乐章，在我怀中轻轻飘摇。\n踮起脚尖，伸手触碰那片秘密天空，\n打开我的门扉，便能将温柔拥抱。",
        "riddle_en": "I dwell among the clouds where warmth and comfort grow,\nThe symphony of pots and pans beneath me softly flow.\nStand on tiptoes, reach up high to touch my secret sky,\nOpen wide my hidden doors—sweet treasures there do lie.",
        "hint": "烹饪爱的味道时，需要仰望的那片天空",
        "location": "厨房壁橱顶部",
        "location_en": "Top of kitchen cabinet",
        "secret_word": "yet grow",
        "word_hint_cn": "你会在那里找到第二个词",
        "word_hint_en": "You'll find the second word there"
    },
    {
        "id": 3,
        "riddle_cn": "晨光中你梳妆，镜中倒影浅浅笑，\n我静卧于你脚边，守着一日开始的美好。\n俯身看我一眼，在这清澈水声之下，\n藏着一份心意，如晨露般温柔闪耀。",
        "riddle_en": "In morning's gentle glow, you grace the mirror's eye,\nI rest beneath your feet where dawn's first moments lie.\nBend down and peek below, where waters softly sing,\nA tender gift awaits like dewdrops glistening.",
        "hint": "每个清晨开始的地方，水声潺潺处",
        "location": "厕所洗手池下面",
        "location_en": "Under the bathroom sink",
        "secret_word": "need air",
        "word_hint_cn": "你会在那里找到第三个词",
        "word_hint_en": "You'll find the third phrase there"
    },
    {
        "id": 4,
        "riddle_cn": "这里是梦开始的地方，也是心最近的港湾，\n每个夜晚枕着星光，我们在此编织浪漫。\n转身触碰那温柔角落，最后的宝藏在等待，\n就像我的心为你守候，在最亲密的瞬间绽开。",
        "riddle_en": "Here dreams unfold their wings, our hearts find sweetest rest,\nEach night we weave romance beneath the stars we're blessed.\nTurn to touch that tender corner where the last treasure lies,\nLike my heart that waits for you—in love's most intimate guise.",
        "hint": "我们每晚相拥入梦的地方，触手可及的温柔",
        "location": "枕头下",
        "location_en": "Under your pillow",
        "secret_word": "no mouth",
        "word_hint_cn": "你会在那里找到最后一个词",
        "word_hint_en": "You'll find the last word there"
    }
]

# The password is "FIRE" - the answer to the final riddle
CORRECT_PASSWORD = "FIRE"

# Final riddle formed by the four clue words: not alive + yet grow + need air + no mouth
FINAL_RIDDLE_CN = "我不是活的(not alive)，但我会生长(yet grow)。\n我没有肺，但我需要空气(need air)。\n我没有嘴巴(no mouth)，\n但我可以吞噬一切。"
FINAL_RIDDLE_EN = "I'm not alive, yet I grow.\nI don't have lungs, yet I need air.\nI don't have a mouth,\nyet I can swallow you whole."

@router.get("/christmas")
async def christmas_treasure_hunt(request: Request):
    """Christmas treasure hunt page"""

    # Read and convert markdown letter to HTML
    letter_path = Path(__file__).parent.parent / "letters" / "2025-12-24_christmas_letter.md"
    with open(letter_path, "r", encoding="utf-8") as f:
        letter_md = f.read()
    letter_html = markdown.markdown(letter_md)

    return templates.TemplateResponse(
        "christmas.html",
        {
            "request": request,
            "riddles": RIDDLES,
            "total_riddles": len(RIDDLES),
            "letter_html": letter_html,
            "final_riddle_cn": FINAL_RIDDLE_CN,
            "final_riddle_en": FINAL_RIDDLE_EN,
            "password": CORRECT_PASSWORD
        }
    )
