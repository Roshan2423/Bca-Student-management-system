# grades/urls.py - Grade Management URL Configuration

from django.urls import path
from . import views

app_name = 'grades'

urlpatterns = [
    # Main Dashboard
    path('', views.GradeDashboardView.as_view(), name='dashboard'),
    
    # Grade Assignment (Teachers/Admin)
    path('assign/', views.AssignGradesView.as_view(), name='assign-grades'),
    
    # Student Grade View
    path('student/', views.StudentGradeView.as_view(), name='student-grades'),
    
    # Reports
    path('reports/', views.GradeReportsView.as_view(), name='reports'),
]