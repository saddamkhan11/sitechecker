from django.urls import path

from . import views

urlpatterns = [
    path("", views.diary, name="diary"),
    path("<int:entry_id>/delete/", views.delete, name="diary_delete"),
    path("report/", views.report, name="diary_report"),
]
