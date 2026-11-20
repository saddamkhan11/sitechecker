from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core import views as core_views

admin.site.site_header = "Construction Checker AI - Admin"
admin.site.site_title = "Construction Checker AI"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", core_views.home, name="home"),
    path("sw.js", core_views.service_worker, name="service_worker"),
    path("manifest.webmanifest", core_views.manifest, name="manifest"),
    path("offline/", core_views.offline, name="offline"),
    path("ui-language/", core_views.set_ui_language, name="set_ui_language"),
    path("accounts/", include("accounts.urls")),
    path("p/", include("projects.urls")),
    path("p/<int:project_id>/chat/", include("chatbot.urls")),
    path("p/<int:project_id>/plan/", include("plans.urls")),
    path("p/<int:project_id>/materials/", include("calculator.urls")),
    path("p/<int:project_id>/checks/", include("checks.urls")),
    path("p/<int:project_id>/diary/", include("diary.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
