from django.urls import path

from . import views

urlpatterns = [
    path("", views.editor, name="plan_editor"),
    path("save/", views.save, name="plan_save"),
    path("check/", views.check, name="plan_check"),
    path("arrange/", views.arrange, name="plan_arrange"),
    path("print/", views.print_view, name="plan_print"),
]
