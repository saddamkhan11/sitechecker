from django.urls import path

from . import views

urlpatterns = [
    path("", views.stage_list, name="check_stages"),
    path("stage/<str:stage>/", views.stage_detail, name="check_stage"),
    path("item/<str:code>/", views.item_detail, name="check_item"),
    path("item/<str:code>/submit/", views.submit, name="check_submit"),
    path("result/<int:check_id>/", views.result, name="check_result"),
    path("result/<int:check_id>/status/", views.status_json, name="check_status"),
]
