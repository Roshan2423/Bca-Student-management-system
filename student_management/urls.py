# student_management/urls.py - Clean URLs without allauth

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

# Import the dashboard views
from dashboard.views import dashboard_redirect, admin_dashboard

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Authentication URLs (clean Django auth - replaces allauth)
    path('accounts/', include('accounts.urls')),
    
    # App URLs - MAIN APPS (these are the ones used by dashboard redirect)
    path('students/', include('students.urls')),
    path('courses/', include('courses.urls')),  # This gives you 'courses:teacher-dashboard'
    path('attendance/', include('attendance.urls')),
    path('grades/', include('grades.urls')),
    
    # NOTE: API endpoints are served under each app's own URL prefix (e.g. students/api/)
    # Removed duplicate namespace includes that caused conflicts with app_name
    
    # Dashboard routing - ROLE-BASED SYSTEM
    path('dashboard/', dashboard_redirect, name='dashboard'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    
    # Home page
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # In development, let django.contrib.staticfiles serve static files from STATICFILES_DIRS
# urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)