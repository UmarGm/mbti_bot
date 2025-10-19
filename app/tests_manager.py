import json
from pathlib import Path
from typing import Dict, Any

# === Базовая структура для тестов ===
BASE_TESTS_DIR = Path(__file__).resolve().parent / "data" / "tests"

def load_test(slug: str) -> Dict[str, Any]:
    """Загружает тест по названию (например 'psych_age')."""
    folder = BASE_TESTS_DIR / slug
    questions_path = folder / "questions.json"
    results_path = folder / "results.json"

    if not questions_path.exists():
        raise FileNotFoundError(f"{questions_path} не найден")
    if not results_path.exists():
        raise FileNotFoundError(f"{results_path} не найден")

    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    return {"slug": slug, "questions": questions, "results": results}

def calc_result(test: Dict[str, Any], traits: list[str]) -> str:
    """Подбирает результат по количеству совпадений."""
    results = test["results"]
    scores = {}
    for rkey, rdata in results.items():
        score = sum(1 for t in traits if t in rdata.get("traits", []))
        scores[rkey] = score
    best_key = max(scores, key=scores.get)
    return results[best_key]["text"]

