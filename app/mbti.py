from collections import Counter
from typing import List, Dict

DIMENSION_PAIRS = [("E","I"),("S","N"),("T","F"),("J","P")]

def mbti_from_traits(traits: List[str]) -> str:
    c = Counter(traits)
    res = []
    for a,b in DIMENSION_PAIRS:
        res.append(a if c[a] >= c[b] else b)
    return "".join(res)

def validate_questions(questions: List[Dict]) -> None:
    for q in questions:
        assert "text" in q and "options" in q
        assert len(q["options"]) == 2
        for opt in q["options"]:
            assert "text" in opt and "trait" in opt
