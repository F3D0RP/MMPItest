import os
import sys
from django.core.management.base import BaseCommand
from mainapp.models import Question, Scale, ScaleQuestion, Norm, ExcludedQuestion, CorrectionFormula

class Command(BaseCommand):
    help = 'Импортирует вопросы, шкалы, связи, нормы, исключения и формулы MMPI из файлов в БД.'

    def handle(self, *args, **options):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        src_dir = os.path.join(base_dir, 'src')
        questions_files = [
            ('questions_f.txt', 'F'),
            ('questions_m.txt', 'M'),
        ]
        # 1. Импорт вопросов
        self.stdout.write('Импорт вопросов...')
        for filename, gender in questions_files:
            path = os.path.join(src_dir, filename)
            with open(path, encoding='utf-8') as f:
                for idx, line in enumerate(f, 1):
                    text = line.strip()
                    if not text:
                        continue
                    Question.objects.update_or_create(
                        number=idx, gender=gender,
                        defaults={'text': text}
                    )
        self.stdout.write(self.style.SUCCESS('Вопросы импортированы.'))

        # 2. Импорт шкал, связей, норм, исключённых вопросов, формул
        self.stdout.write('Импорт шкал и связей...')
        sys.path.insert(0, src_dir)
        import list as mmpi_list

        # Шкалы
        for code, name in mmpi_list.psychology_scales.items():
            Scale.objects.update_or_create(code=code, defaults={'name': name})

        # Связи шкала-вопрос
        for scale_code, data in mmpi_list.scales.items():
            # Попытка получить шкалу, если нет — создать с техническим именем
            scale, _ = Scale.objects.get_or_create(
                code=scale_code,
                defaults={'name': mmpi_list.psychology_scales.get(scale_code, scale_code)}
            )
            for answer_type in ('yes', 'no'):
                for qnum in data.get(answer_type, []):
                    # Определяем пол: если шкала с -Ж или -М, то только для соответствующего пола
                    if scale_code.endswith('-Ж'):
                        gender = 'F'
                        code = scale_code[:-2]
                    elif scale_code.endswith('-М'):
                        gender = 'M'
                        code = scale_code[:-2]
                    else:
                        gender = None
                        code = scale_code
                    if gender:
                        try:
                            question = Question.objects.get(number=qnum, gender=gender)
                        except Question.DoesNotExist:
                            continue
                    else:
                        # Пробуем оба пола
                        for g in ['F', 'M']:
                            try:
                                question = Question.objects.get(number=qnum, gender=g)
                            except Question.DoesNotExist:
                                continue
                            ScaleQuestion.objects.update_or_create(
                                scale=scale, question=question, answer_type=answer_type
                            )
                        continue
                    ScaleQuestion.objects.update_or_create(
                        scale=scale, question=question, answer_type=answer_type
                    )
        self.stdout.write(self.style.SUCCESS('Шкалы и связи импортированы.'))

        # Нормы
        self.stdout.write('Импорт норм...')
        for gender, scales in mmpi_list.norms.items():
            for code, (mean, sd) in scales.items():
                try:
                    scale = Scale.objects.get(code=code)
                except Scale.DoesNotExist:
                    continue
                Norm.objects.update_or_create(
                    scale=scale, gender=gender,
                    defaults={'mean': mean, 'sd': sd}
                )
        self.stdout.write(self.style.SUCCESS('Нормы импортированы.'))

        # Исключённые вопросы
        self.stdout.write('Импорт исключённых вопросов...')
        for qnum in mmpi_list.excluded_questions:
            for gender in ['F', 'M']:
                try:
                    question = Question.objects.get(number=qnum, gender=gender)
                except Question.DoesNotExist:
                    continue
                ExcludedQuestion.objects.update_or_create(question=question)
        self.stdout.write(self.style.SUCCESS('Исключённые вопросы импортированы.'))

        # Формулы коррекции
        self.stdout.write('Импорт формул коррекции...')
        for code, (formula, value) in mmpi_list.correction_formulas.items():
            try:
                scale = Scale.objects.get(code=code)
            except Scale.DoesNotExist:
                continue
            CorrectionFormula.objects.update_or_create(
                scale=scale, defaults={'formula': formula, 'value': value}
            )
        self.stdout.write(self.style.SUCCESS('Формулы коррекции импортированы.'))

        self.stdout.write(self.style.SUCCESS('Импорт MMPI завершён.')) 