# courses/urls.py

from django.urls import path
from . import views

app_name = 'courses'

urlpatterns = [
    # Main dashboard routing
    path('', views.CourseHomeView.as_view(), name='home'),
    path('list/', views.CourseHomeView.as_view(), name='list'),
    
    # Admin course management - NEW
    path('management/', views.CourseManagementView.as_view(), name='course-management'),
    path('assign-teacher/', views.assign_teacher_to_subject, name='assign-teacher'),
    
    # Student dashboard and course access
    path('student/dashboard/', views.StudentDashboardView.as_view(), name='student-dashboard'),
    path('student/assignments/', views.StudentAssignmentsView.as_view(), name='student-assignments'),
    path('subject/<str:subject_code>/', views.SubjectDetailView.as_view(), name='subject-detail'),
    path('assignment/<str:assignment_id>/submit/', views.SubmitAssignmentView.as_view(), name='submit-assignment'),
    
    # Teacher dashboard and course management
    path('teacher/dashboard/', views.TeacherDashboardView.as_view(), name='teacher-dashboard'),
    path('subject/<str:subject_code>/students/', views.SubjectStudentsView.as_view(), name='subject-students'),
    path('subject/<str:subject_code>/submissions/', views.SubjectSubmissionsView.as_view(), name='subject-submissions'),
    path('upload-material/<str:subject_code>/', views.UploadMaterialView.as_view(), name='upload-material'),
    path('create-assignment/<str:subject_code>/', views.CreateAssignmentView.as_view(), name='create-assignment'),
    
    # Assignment and material file operations
    path('assignment/<str:assignment_id>/', views.AssignmentDetailView.as_view(), name='assignment-detail'),
    path('assignment/<str:assignment_id>/submissions/', views.AssignmentSubmissionsView.as_view(), name='assignment-submissions'),
    
    # File download and view URLs
    path('assignment/<str:assignment_id>/download/', views.download_assignment_file, name='download-assignment-file'),
    path('assignment/<str:assignment_id>/view/', views.view_assignment_file, name='view-assignment-file'),
    path('submission/<str:submission_id>/download/', views.download_submission_file, name='download-submission-file'),
    path('material/<str:material_id>/download/', views.download_material_file, name='download-material-file'),
    path('material/<str:material_id>/view/', views.view_material_file, name='view-material-file'),
    
    # Teacher management routes
    path('teachers/', views.TeacherListView.as_view(), name='teacher-list'),
    path('teacher/create/', views.TeacherCreateView.as_view(), name='teacher-create'),
    path('teacher/<str:teacher_id>/', views.TeacherDetailView.as_view(), name='teacher-detail'),
    path('teacher/<str:teacher_id>/edit/', views.TeacherEditView.as_view(), name='teacher-edit'),
    path('teacher/<str:teacher_id>/delete/', views.TeacherDeleteView.as_view(), name='teacher-delete'),
    path('teacher/<str:teacher_id>/password/', views.TeacherPasswordChangeView.as_view(), name='teacher-password-change'),
    
    # Teacher Active/Inactive Management
    path('teacher/<str:teacher_id>/toggle-status/', views.toggle_teacher_status, name='toggle-teacher-status'),
    
    # API endpoints
    path('api/stats/', views.course_dashboard_stats, name='api-stats'),
    path('api/teacher-stats/', views.teacher_dashboard_stats, name='api-teacher-stats'),

    # Submission approval/rejection
    path('submission/<str:submission_id>/approve/', views.approve_submission, name='approve-submission'),
    path('submission/<str:submission_id>/reject/', views.reject_submission, name='reject-submission'),
    path('submission/<str:submission_id>/feedback/', views.submission_feedback_view, name='submission-feedback'),

    # Student submission view URL
    path('assignment/<str:assignment_id>/my-submission/view/', views.view_my_submission, name='view-my-submission'),

     # Material edit/delete URLs - ADD THESE
    path('material/<str:material_id>/edit/', views.edit_material, name='edit-material'),
    path('material/<str:material_id>/delete/', views.delete_material, name='delete-material'),
    
    # Assignment edit/delete URLs - ADD THESE  
    path('assignment/<str:assignment_id>/edit/', views.edit_assignment, name='edit-assignment'),
    path('assignment/<str:assignment_id>/delete/', views.delete_assignment, name='delete-assignment'),

    # Fee Management URLs - ADD THESE
    path('fees/', views.StudentFeeManagementView.as_view(), name='fee-management'),
    path('fees/mark-payment/', views.mark_fee_payment, name='mark-fee-payment'),
    path('student-payment-history/<str:student_id>/', views.student_payment_history, name='student-payment-history'),
    path('teacher-salary-history/<str:teacher_id>/', views.teacher_salary_history, name='teacher-salary-history'),
    
    # Salary Management URLs - ADD THESE  
    path('salaries/', views.TeacherSalaryManagementView.as_view(), name='salary-management'),
    path('salaries/mark-payment/', views.mark_salary_payment, name='mark-salary-payment'),
    path('salaries/generate/', views.generate_monthly_salaries, name='generate-salaries'),


    # --- Minimal routes so existing template links work ---
    path('create/', views.CourseCreateView.as_view(), name='add'),
    path('<str:course_code>/', views.CourseDetailView.as_view(), name='detail'),
    path('<str:course_code>/edit/', views.CourseEditView.as_view(), name='edit'),
    path('<str:course_code>/enroll/', views.enroll_students, name='enroll'),
    path('teacher/add/', views.TeacherQuickAddView.as_view(), name='teacher-add'),

]