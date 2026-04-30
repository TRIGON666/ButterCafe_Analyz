"""
URL configuration for buttercafe project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.static import serve
from cafe.admin_dashboard import analytics_dashboard, analytics_dashboard_pdf, metabase_dashboard

urlpatterns = [
    path('admin/analytics/', admin.site.admin_view(analytics_dashboard), name='admin_analytics_dashboard'),
    path('admin/analytics/pdf/', admin.site.admin_view(analytics_dashboard_pdf), name='admin_analytics_dashboard_pdf'),
    path('admin/metabase/', admin.site.admin_view(metabase_dashboard), name='admin_metabase_dashboard'),
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('cafe.urls')),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()

if settings.SERVE_MEDIA_FILES:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
