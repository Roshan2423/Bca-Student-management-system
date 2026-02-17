"""
Comprehensive tests for the attendance app.
Tests: view access control, URL resolution, role-based permissions.
"""
from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from test_helpers import SafeClient as Client


class AttendanceURLResolutionTest(TestCase):
    """Test that all attendance URLs resolve correctly"""

    def test_dashboard_url(self):
        url = reverse('attendance:dashboard')
        self.assertEqual(url, '/attendance/')

    def test_mark_students_url(self):
        url = reverse('attendance:mark-students')
        self.assertEqual(url, '/attendance/mark-students/')

    def test_teacher_self_mark_url(self):
        url = reverse('attendance:teacher-self-mark')
        self.assertEqual(url, '/attendance/teacher-self-mark/')

    def test_mark_teachers_url(self):
        url = reverse('attendance:mark-teachers')
        self.assertEqual(url, '/attendance/mark-teachers/')

    def test_reports_url(self):
        url = reverse('attendance:reports')
        self.assertEqual(url, '/attendance/reports/')

    def test_student_view_url(self):
        url = reverse('attendance:student-view')
        self.assertEqual(url, '/attendance/student/')


class AttendanceDashboardViewTest(TestCase):
    """Test the attendance dashboard view"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )
        self.teacher = User.objects.create_user(
            email='teacher@test.com', password='pass123', role='teacher'
        )
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('attendance:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_dashboard_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('attendance:dashboard'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_dashboard_accessible_by_teacher(self):
        self.client.login(email='teacher@test.com', password='pass123')
        response = self.client.get(reverse('attendance:dashboard'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login


class MarkStudentAttendanceViewTest(TestCase):
    """Test marking student attendance"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )
        self.teacher = User.objects.create_user(
            email='teacher@test.com', password='pass123', role='teacher'
        )
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )

    def test_mark_student_requires_login(self):
        response = self.client.get(reverse('attendance:mark-students'))
        self.assertEqual(response.status_code, 302)

    def test_mark_student_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('attendance:mark-students'))
        self.assertNotEqual(response.status_code, 302)

    def test_mark_student_accessible_by_teacher(self):
        self.client.login(email='teacher@test.com', password='pass123')
        response = self.client.get(reverse('attendance:mark-students'))
        self.assertNotEqual(response.status_code, 302)


class TeacherSelfAttendanceViewTest(TestCase):
    """Test teacher self-attendance marking"""

    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            email='teacher@test.com', password='pass123', role='teacher'
        )
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )

    def test_self_mark_requires_login(self):
        response = self.client.get(reverse('attendance:teacher-self-mark'))
        self.assertEqual(response.status_code, 302)

    def test_self_mark_accessible_by_teacher(self):
        self.client.login(email='teacher@test.com', password='pass123')
        response = self.client.get(reverse('attendance:teacher-self-mark'))
        self.assertNotEqual(response.status_code, 302)


class StudentAttendanceViewTest(TestCase):
    """Test student attendance view"""

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )
        self.teacher = User.objects.create_user(
            email='teacher@test.com', password='pass123', role='teacher'
        )

    def test_student_attendance_requires_login(self):
        response = self.client.get(reverse('attendance:student-view'))
        self.assertEqual(response.status_code, 302)

    def test_student_can_view_own_attendance(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.get(reverse('attendance:student-view'))
        self.assertNotEqual(response.status_code, 302)


class AttendanceReportsViewTest(TestCase):
    """Test attendance reports view"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )

    def test_reports_requires_login(self):
        response = self.client.get(reverse('attendance:reports'))
        self.assertEqual(response.status_code, 302)

    def test_reports_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('attendance:reports'))
        self.assertNotEqual(response.status_code, 302)


class QuickMarkAttendanceSecurityTest(TestCase):
    """Test that AJAX attendance endpoints require authentication (bug fix verified)"""

    def setUp(self):
        self.client = Client()

    def test_quick_mark_requires_login(self):
        """Bug fix: Previously had no @login_required"""
        response = self.client.post(
            reverse('attendance:quick-mark'),
            data='{"person_type":"student","person_id":"STU001","is_present":true,"date":"2025-01-01"}',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_approve_requires_login(self):
        """Bug fix: Previously had no @login_required"""
        response = self.client.post(
            reverse('attendance:approve-teacher-attendance'),
            {'attendance_id': 'fake', 'action': 'approve'}
        )
        self.assertEqual(response.status_code, 302)  # Redirects to login
