from django.contrib import admin
from django.urls import path, include

from transport.auth_views import SignupView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/inscription/", SignupView.as_view(), name="signup"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("transport.urls")),
]
