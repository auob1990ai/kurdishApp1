import re
from difflib import get_close_matches

# Conservative starter lexicon. It is intentionally small: only high-confidence
# substitutions are automatic, while uncertain words are left unchanged.
COMMON = {
    "ئەمەش": ["ئەمەش"], "ئەمە": ["ئەمە"], "ئەوە": ["ئەوە"], "ئێمە": ["ئێمە"],
    "ئێوە": ["ئێوە"], "ئەوان": ["ئەوان"], "چۆن": ["چۆن"], "بۆچی": ["بۆچی"],
    "بەڵێ": ["بەڵێ"], "نەخێر": ["نەخێر"], "سوپاس": ["سوپاس"], "تکایە": ["تکایە"],
    "باشە": ["باشە"], "زۆر": ["زۆر"], "هەموو": ["هەموو"], "هەرگیز": ["هەرگیز"],
    "دەبێت": ["دەبێت"], "دەتوانێت": ["دەتوانێت"], "دەکات": ["دەکات"],
    "دەچێت": ["دەچێت"], "دەخوات": ["دەخوات"], "دەنووسێت": ["دەنووسێت"],
    "خوێندن": ["خوێندن"], "زانکۆ": ["زانکۆ"], "مامۆستا": ["مامۆستا"],
    "قوتابخانە": ["قوتابخانە"], "کتێب": ["کتێب"], "کوردستان": ["کوردستان"],
    "کوردی": ["کوردی"], "سۆرانی": ["سۆرانی"], "زمان": ["زمان"],
    "نووسین": ["نووسین"], "وێنە": ["وێنە"], "دەنگ": ["دەنگ"], "دەق": ["دەق"],
    "بەرنامە": ["بەرنامە"], "ئەپ": ["ئەپ"], "وێبسایت": ["وێبسایت"],
    "تەکنەلۆجیا": ["تەکنەلۆجیا"], "هۆشی دەستکرد": ["هۆشی دەستکرد"],
}

# Common OCR/ASR confusions seen around Arabic-script Kurdish. Only apply when
# the result is an unambiguous close match.
ALIASES = {
    "ئەمەیە": "ئەمەیە", "ئەمەی": "ئەمەی", "ده‌بێت": "دەبێت", "دەبێ": "دەبێت",
    "دەتوانێ": "دەتوانێت", "ده‌توانێت": "دەتوانێت", "دەکاتە": "دەکاتە",
    "كوردی": "کوردی", "كوردستان": "کوردستان", "كه‌": "کە", "كه": "کە",
}

WORD_RE = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]+|[A-Za-z]+")


def normalize_sorani(text: str) -> str:
    # Arabic/Persian Unicode variants commonly introduced by OCR.
    repl = str.maketrans({"ي":"ی", "ى":"ی", "ك":"ک", "ـ":"", "ۀ":"ە", "ة":"ە"})
    text = text.translate(repl)
    text = text.replace("\u200c", "‌")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([،؛؟!.,:;])", r"\1", text)
    return text.strip()


def correct_sorani(text: str):
    text = normalize_sorani(text)
    corrections = []
    words = re.findall(r"\S+", text)
    out = []
    vocab = list(COMMON.keys())
    for raw in words:
        leading = re.match(r"^([^\w\u0600-\u06ff]*)(.*?)([^\w\u0600-\u06ff]*)$", raw)
        if not leading:
            out.append(raw); continue
        pre, core, post = leading.groups()
        if not core:
            out.append(raw); continue
        if core in ALIASES:
            new = ALIASES[core]
            corrections.append({"from": core, "to": new, "confidence": 0.99})
            out.append(pre + new + post); continue
        # Avoid changing short words; fuzzy matching only for longer tokens.
        if len(core) >= 5 and core not in COMMON:
            candidates = get_close_matches(core, vocab, n=2, cutoff=0.88)
            if candidates and candidates[0] != core:
                new = candidates[0]
                corrections.append({"from": core, "to": new, "confidence": 0.88})
                out.append(pre + new + post); continue
        out.append(raw)
    return " ".join(out), corrections
