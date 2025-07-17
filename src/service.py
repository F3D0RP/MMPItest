from django.db.models import Q
from mainapp.models import Question, Scale, ScaleQuestion, Norm, ExcludedQuestion, CorrectionFormula
import math
import random

def get_scales():
    return {s.code: s.name for s in Scale.objects.all()}

def get_norms():
    norms = {}
    for n in Norm.objects.all():
        norms.setdefault(n.gender, {})[n.scale.code] = (n.mean, n.sd)
    return norms

def get_correction_formulas():
    return {cf.scale.code: (cf.formula, cf.value) for cf in CorrectionFormula.objects.all()}

def get_excluded_questions():
    return set(eq.question.number for eq in ExcludedQuestion.objects.all())

def custom_round(value):
    fractional = value - int(value)
    if fractional >= 0.4:
        return int(value) + 1
    else:
        return int(value)

def calc_delta_k(factor: float, k_score: int) -> int:
    if factor == 0:
        return 0
    raw_value = factor * k_score
    sign = 1 if raw_value >= 0 else -1
    rounded = custom_round(abs(raw_value))
    return sign * rounded

def apply_k_correction(raw_scores: dict[str, int]) -> dict[str, int]:
    corrected_scores = {}
    k_score = raw_scores.get("K", 0)
    correction_formulas = get_correction_formulas()
    for scale, raw in raw_scores.items():
        if scale in correction_formulas:
            _, factor = correction_formulas[scale]
            delta_k = calc_delta_k(factor, k_score)
            corrected_scores[scale] = raw + delta_k
        else:
            corrected_scores[scale] = raw
    return corrected_scores

def compute_raw_scores(user_answers: dict[int, str], gender: str) -> dict[str, int]:
    results = {"?": 0}
    already_counted_questions = set()
    for scale in Scale.objects.all():
        code = scale.code
        if code in {"B5-М", "B5-Ж"}:
            if (gender == "M" and code != "B5-М") or (gender == "F" and code != "B5-Ж"):
                continue
            actual_scale = "B5"
        else:
            actual_scale = code
        score = 0
        for answer_type in ("yes", "no"):
            sqs = ScaleQuestion.objects.filter(scale=scale, answer_type=answer_type)
            for sq in sqs:
                q = sq.question
                qnum = q.number
                if qnum not in user_answers:
                    continue
                user_response = user_answers[qnum].strip().lower()
                if user_response == "не знаю":
                    if qnum not in already_counted_questions:
                        results["?"] += 1
                        already_counted_questions.add(qnum)
                    continue
                expected = "верно" if answer_type == "yes" else "неверно"
                if user_response == expected:
                    score += 1
        results[actual_scale] = results.get(actual_scale, 0) + score
    return results

def evaluate_test(answers: dict, gender: str):
    raw_scores = compute_raw_scores(answers, gender)
    corrected_scores = apply_k_correction(raw_scores)
    k_score = raw_scores.get("K", 0)
    results = []
    norms = get_norms()
    correction_formulas = get_correction_formulas()
    scales = get_scales()
    for scale in Scale.objects.all():
        code = scale.code
        if code in {"B5-М", "B5-Ж"}:
            if (gender == "M" and code == "B5-М") or (gender == "F" and code == "B5-Ж"):
                sc = "B5"
            else:
                continue
        else:
            sc = code
        raw = raw_scores.get(sc)
        if raw is None:
            continue
        corrected = corrected_scores.get(sc, raw)
        formula, factor = correction_formulas.get(sc, ("", 0))
        delta_k = calc_delta_k(factor, k_score)
        mean, sd = norms.get(gender, {}).get(sc, (None, None))
        if mean is not None and sd:
            t_score = round(50 + 10 * (corrected - mean) / sd, 2)
        else:
            t_score = None
        name = scales.get(sc, "Неизвестная шкала")
        results.append({
            "scale": sc,
            "name": name,
            "raw": raw,
            "corrected": corrected,
            "t_score": t_score,
            "delta_k": delta_k,
            "formula": formula,
            "mean": mean,
            "sd": sd,
        })
    return {
        "results": results,
        "dont_know_count": raw_scores.get("?", 0),
    }
