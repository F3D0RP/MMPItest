from django.contrib import admin
from .models import TestResult

@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('uuid', 
    readonly_fields = ('uuid', 'created_at', 'results')