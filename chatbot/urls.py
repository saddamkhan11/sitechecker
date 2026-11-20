from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat, name="chat"),
    path("send/", views.send, name="chat_send"),
    path("voice/", views.voice, name="chat_voice"),
    path("language/", views.set_language, name="chat_language"),
]
