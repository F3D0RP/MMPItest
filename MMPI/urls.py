from django.urls import path, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from mainapp.views import IndexView, StartTestView, TestPageView, SubmitTestView, SubmitTestAPI
from mainapp.views import result_view
from django.contrib import admin


schema_view = get_schema_view(
    openapi.Info(
        title="Your API",
        default_version='v1',
        description="API для тестирования",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="your-email@example.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('start/', StartTestView.as_view(), name='start_test'),
    path('test/', TestPageView.as_view(), name='test_page'),
    path('submit/', SubmitTestView.as_view(), name='submit_test'),
    path('api/submit-test/', SubmitTestAPI.as_view(), name='submit-test-api'),
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('results/<uuid:uuid>/', result_view, name='result_view'),
    path('admin/', admin.site.urls),

]

handler404 = 'mainapp.views.custom_404_view'

