from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.renderers import TemplateHTMLRenderer
from django.shortcuts import redirect
import json

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .serializers import SubmitTestSerializer
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import TestResult, Question, Scale, ScaleQuestion, Norm, ExcludedQuestion, CorrectionFormula
from django.contrib import messages
from django import forms
import random
import string
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from collections import defaultdict
from datetime import timedelta
from django.utils import timezone


def result_view(request, uuid):
    test_result = get_object_or_404(TestResult, uuid=uuid)
    results = test_result.results
    dont_know_count = None
    if isinstance(results, dict) and 'results' in results and 'dont_know_count' in results:
        dont_know_count = results['dont_know_count']
        results = results['results']
    return render(request, 'results.html', {
        'results': results,
        'created_at': test_result.created_at,
        'dont_know_count': dont_know_count,
        'show_result_link': False
    })


def get_questions_from_db(gender):
    return list(Question.objects.filter(gender=gender).order_by('number').values_list('text', flat=True))


def get_questions_randomized(gender):
    questions = list(Question.objects.filter(gender=gender))
    random.shuffle(questions)
    return [(q.number, q.text) for q in questions]


def get_scales_dict():
    return {s.code: s.name for s in Scale.objects.all()}


def get_norms_dict():
    norms = {}
    for n in Norm.objects.all():
        norms.setdefault(n.gender, {})[n.scale.code] = (n.mean, n.sd)
    return norms


def get_correction_formulas_dict():
    return {cf.scale.code: (cf.formula, cf.value) for cf in CorrectionFormula.objects.all()}


def get_scale_questions_map():
    # scale_code -> {'yes': set(qnum), 'no': set(qnum)}
    scale_q_map = defaultdict(lambda: {'yes': set(), 'no': set()})
    sqs = ScaleQuestion.objects.select_related('scale', 'question').all()
    for sq in sqs:
        scale_q_map[sq.scale.code][sq.answer_type].add(sq.question.number)
    return scale_q_map


def custom_round(value):
    fractional = value - int(value)
    if fractional >= 0.4:
        return int(value) + 1
    else:
        return int(value)


def calc_delta_k(factor, k_score):
    if factor == 0:
        return 0
    raw_value = factor * k_score
    sign = 1 if raw_value >= 0 else -1
    rounded = custom_round(abs(raw_value))
    return sign * rounded


def apply_k_correction(raw_scores, correction_formulas):
    corrected_scores = {}
    k_score = raw_scores.get("K", 0)
    for scale, raw in raw_scores.items():
        if scale in correction_formulas:
            _, factor = correction_formulas[scale]
            delta_k = calc_delta_k(factor, k_score)
            corrected_scores[scale] = raw + delta_k
        else:
            corrected_scores[scale] = raw
    return corrected_scores


def compute_raw_scores(user_answers, gender, scale_q_map):
    results = {"?": 0}
    already_counted_questions = set()
    for code in scale_q_map:
        # B5-М/Ж — только для соответствующего пола
        if code in {"B5-М", "B5-Ж"}:
            if (gender == "M" and code != "B5-М") or (gender == "F" and code != "B5-Ж"):
                continue
            actual_scale = "B5"
        else:
            actual_scale = code
        score = 0
        for answer_type in ("yes", "no"):
            for qnum in scale_q_map[code][answer_type]:
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


def evaluate_test(answers, gender):
    scale_q_map = get_scale_questions_map()
    correction_formulas = get_correction_formulas_dict()
    norms = get_norms_dict()
    scales = get_scales_dict()
    raw_scores = compute_raw_scores(answers, gender, scale_q_map)
    corrected_scores = apply_k_correction(raw_scores, correction_formulas)
    k_score = raw_scores.get("K", 0)
    results = []
    
    def scale_sort_key(code):
        # L, K, F — всегда в начале, в порядке L, K, F
        if code == "L":
            return (0, 0)
        if code == "K":
            return (0, 1)
        if code == "F":
            return (0, 2)
        # B1, B2, ...
        if code.startswith("B") and code[1:].replace("-М","").replace("-Ж","").isdigit():
            return (1, int(''.join(filter(str.isdigit, code))))
        # A1, A2, ...
        if code.startswith("A") and code[1:].isdigit():
            return (2, int(code[1:]))
        # Остальные — в конец
        return (3, code)
    
    for code in sorted(scale_q_map, key=scale_sort_key):
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


class SubmitTestAPI(APIView):
    @swagger_auto_schema(
        request_body=SubmitTestSerializer,
        responses={200: openapi.Response('Success', SubmitTestSerializer)},
        operation_description="Отправка ответов на тест, получение результатов"
    )
    def post(self, request):
        serializer = SubmitTestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        gender = serializer.validated_data["gender"]
        raw_answers = serializer.validated_data["answers"]
        answer_map = {"1": "верно", "0": "неверно", "": "не знаю"}
        answers = {int(k): answer_map[v] for k, v in raw_answers.items()}
        result_data = evaluate_test(answers, gender)
        return Response({
            "results": result_data["results"],
            "dont_know_count": result_data["dont_know_count"],
        }, status=status.HTTP_200_OK)


def load_questions(gender):
    # Возвращает вопросы в случайном порядке
    questions = list(Question.objects.filter(gender=gender))
    random.shuffle(questions)
    return [q.text for q in questions]


class IndexView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'index.html'

    def get(self, request):
        return Response({})


class StartTestView(APIView):
    def post(self, request):
        gender = request.data.get("gender")
        if gender not in ("M", "F"):
            return redirect('index')
        request.session['gender'] = gender
        # Формируем случайный порядок вопросов и сохраняем в сессии
        question_numbers = list(Question.objects.filter(gender=gender).values_list('number', flat=True))
        random.shuffle(question_numbers)
        request.session['question_order'] = question_numbers
        return redirect('test_page')


class TestPageView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'test_page.html'

    def get(self, request):
        gender = request.session.get('gender')
        if not gender:
            return redirect('index')
        question_order = request.session.get('question_order')
        if not question_order:
            # fallback: если нет порядка, сгенерировать новый
            question_numbers = list(Question.objects.filter(gender=gender).values_list('number', flat=True))
            random.shuffle(question_numbers)
            question_order = question_numbers
            request.session['question_order'] = question_order
        questions = list(Question.objects.filter(gender=gender, number__in=question_order))
        questions_dict = {q.number: q.text for q in questions}
        questions_list = [(num, questions_dict[num]) for num in question_order]
        return Response({
            "gender": gender,
            "questions": questions_list,
        })


class SubmitTestView(APIView):
    renderer_classes = [TemplateHTMLRenderer]
    template_name = 'results.html'

    def post(self, request):
        user_answers_json = request.data.get("answers")
        gender = request.session.get('gender')
        question_order = request.session.get('question_order')
        if not user_answers_json or not gender or not question_order:
            return redirect('index')
        user_answers = json.loads(user_answers_json)
        # answers: {номер: ответ}, порядок вопросов уже учтён
        answers = {int(k): v for k, v in user_answers.items()}
        data = evaluate_test(answers, gender)
        results = data["results"]
        dont_know_count = data["dont_know_count"]
        for res in results:
            t_score = res["t_score"]
            if isinstance(t_score, (int, float)):
                clamped = max(0, min(120, t_score))
                res["t_score_position"] = round(clamped / 1.2, 2)
            else:
                res["t_score_position"] = None
            res["is_additional"] = res["scale"].startswith("A")
        results_to_save = {
            'results': results,
            'dont_know_count': dont_know_count
        }
        test_result = TestResult.objects.create(
            results=results_to_save
        )
        # Обновляем время создания, добавляя 3 часа
        test_result.created_at = timezone.now() + timedelta(hours=3)
        test_result.save(update_fields=['created_at'])
        print("Original time:", timezone.now())
        print("Adjusted time:", test_result.created_at)
        # Очищаем порядок вопросов после завершения теста
        if 'question_order' in request.session:
            del request.session['question_order']
        return Response({
            "results": results,
            "gender": gender,
            "dont_know_count": dont_know_count,
            "result_link": request.build_absolute_uri(f"/results/{test_result.uuid}/"),
            "show_result_link": True,
            "created_at": test_result.created_at
        }, template_name='results.html')


def custom_404_view(request, exception):
    return redirect('index')
