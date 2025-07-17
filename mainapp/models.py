from django.db import models
import uuid

class TestResult(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    results = models.JSONField()  # { "scale1": value, ... }
    created_at = models.DateTimeField(auto_now_add=True)

class Question(models.Model):
    GENDER_CHOICES = [
        ("F", "Female"),
        ("M", "Male"),
    ]
    number = models.PositiveIntegerField()
    text = models.TextField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)

    def __str__(self):
        return f"{self.number} ({self.gender}): {self.text[:50]}"

class Scale(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code}: {self.name}"

class ScaleQuestion(models.Model):
    ANSWER_TYPE_CHOICES = [
        ("yes", "Yes"),
        ("no", "No"),
    ]
    scale = models.ForeignKey(Scale, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_type = models.CharField(max_length=3, choices=ANSWER_TYPE_CHOICES)

    class Meta:
        unique_together = ("scale", "question", "answer_type")

class Norm(models.Model):
    GENDER_CHOICES = [
        ("F", "Female"),
        ("M", "Male"),
    ]
    scale = models.ForeignKey(Scale, on_delete=models.CASCADE)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    mean = models.FloatField()
    sd = models.FloatField()

    class Meta:
        unique_together = ("scale", "gender")

class ExcludedQuestion(models.Model):
    question = models.OneToOneField(Question, on_delete=models.CASCADE)

class CorrectionFormula(models.Model):
    scale = models.OneToOneField(Scale, on_delete=models.CASCADE)
    formula = models.CharField(max_length=50)
    value = models.FloatField()