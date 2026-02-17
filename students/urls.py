# students/urls.py - Enhanced with password management and status management routes

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# API Router for REST endpoints
router = DefaultRouter()
router.register(r'students', views.StudentViewSet, basename='student')
router.register(r'documents', views.StudentDocumentViewSet, basename='document')

app_name = 'students'

urlpatterns = [
    # Web interface routes
    path('', views.StudentListView.as_view(), name='list'),
    path('create/', views.StudentCreateView.as_view(), name='create'),
    
    # Random Forest Algorithm Analysis - MUST come before parameterized routes
    path('random-forest-analysis/', views.random_forest_analysis_view, name='random-forest-analysis'),
    
    # K-Means Clustering Analysis - MUST come before parameterized routes
    path('kmeans-clustering/', views.kmeans_clustering_view, name='kmeans-clustering'),
    
    # Bulk actions - MUST come before parameterized routes
    path('bulk-status/', views.bulk_activate_students, name='bulk-status'),
    path('bulk-semester/', views.bulk_update_semester, name='bulk-semester'),
    
    # API routes - MUST come before parameterized routes
    path('api/', include(router.urls)),
    path('api/stats/', views.student_dashboard_stats, name='api-stats'),
    
    # Parameterized routes (these can conflict with specific routes if placed above)
    path('<str:pk>/', views.StudentDetailView.as_view(), name='detail'),
    path('<str:pk>/edit/', views.StudentUpdateView.as_view(), name='update'),
    path('<str:pk>/delete/', views.StudentDeleteView.as_view(), name='delete'),
    path('<str:pk>/password/', views.StudentPasswordChangeView.as_view(), name='password-change'),
    path('<str:pk>/toggle-status/', views.toggle_student_status, name='toggle-status'),
    
]