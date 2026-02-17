# attendance/urls.py - URL Configuration for Simplified Attendance System

from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    # Main Dashboard
    path('', views.AttendanceDashboardView.as_view(), name='dashboard'),
    
    # Mark Attendance
    path('mark-students/', views.MarkStudentAttendanceView.as_view(), name='mark-students'),
    path('mark-teachers/', views.MarkTeacherAttendanceView.as_view(), name='mark-teachers'),
    path('teacher-self-mark/', views.TeacherSelfAttendanceView.as_view(), name='teacher-self-mark'),
    path('approve-teacher-attendance/', views.approve_teacher_attendance, name='approve-teacher-attendance'),
    
    # Student View
    path('student/', views.StudentAttendanceView.as_view(), name='student-view'),
    
    # Reports
    path('reports/', views.AttendanceReportsView.as_view(), name='reports'),
    
    # AJAX Endpoints
    path('quick-mark/', views.quick_mark_attendance, name='quick-mark'),
]