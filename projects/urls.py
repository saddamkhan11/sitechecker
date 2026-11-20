from django.urls import path

from . import views

urlpatterns = [
    path("", views.project_list, name="project_list"),
    path("new/", views.project_new, name="project_new"),
    path("<int:project_id>/", views.project_detail, name="project_detail"),
    path("<int:project_id>/stage/<str:stage>/", views.stage_status, name="stage_status"),
    path("<int:project_id>/rules/", views.rules_list, name="rules_list"),
]
