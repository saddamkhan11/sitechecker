from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from .forms import PhoneLoginForm, SignupForm


def signup(request):
    if request.user.is_authenticated:
        return redirect("project_list")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save(commit=False)
        user.ui_language = request.session.get("ui_language", user.ui_language)  # keep the language picked before signup
        user.save()
        login(request, user)
        return redirect("project_list")
    return render(request, "accounts/signup.html", {"form": form})


class PhoneLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = PhoneLoginForm
    redirect_authenticated_user = True
