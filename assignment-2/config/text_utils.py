"""Tiny tokenizer shared by memory scoring and the offline embedding fallback."""
import re

STOPWORDS = set(
    "a an the is are was were be been am i me my you your we our it its of to in on for and or but "
    "with at by from as that this these those do does did can could should would will shall may "
    "what which who whom how when where why about into than then so if not no any some there their "
    "have has had tell told please also just very much many more most us "
    "policy policies rule rules handbook regulation regulations information info student students".split()
)

_SYNONYMS = {
    "paid": "pay", "paying": "pay", "payment": "pay", "payments": "pay", "payable": "pay",
    "fees": "fee", "programme": "program", "programmes": "program", "programs": "program",
    "scholarships": "scholarship", "eligible": "eligibility", "attend": "attendance",
    "exams": "exam", "examination": "exam", "examinations": "exam", "electives": "elective",
    "courses": "course", "tickets": "ticket", "prefer": "preference", "prefers": "preference",
    "preferences": "preference", "preferred": "preference",
}


def stem(word: str) -> str:
    word = _SYNONYMS.get(word, word)
    for suffix in ("ing", "ed", "es", "s"):
        if len(word) > 4 and word.endswith(suffix):
            word = word[: -len(suffix)]
            break
    return _SYNONYMS.get(word, word)


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]
