"""
§5/§11: login + logout. Django's built-in auth views do the real work —
LOGIN_URL/LOGIN_REDIRECT_URL/LOGOUT_REDIRECT_URL are already set in
config/settings/base.py, so there is nothing to hand-roll here.
"""

from django.contrib.auth import views as auth_views
from django.urls import path

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
