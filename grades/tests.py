"""
Comprehensive tests for the grades app.
Tests: view access control, URL resolution, role-based permissions.
"""
from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from test_helpers import SafeClient as Client


class GradeURLResolutionTest(TestCase):
    """Test that all grade URLs resolve correctly"""

    def test_dashboard_url(self):
        url = reverse('grades:dashboard')
        self.assertEqual(url, '/grades/')

    def test_assign_grades_url(self):
        url = reverse('grades:assign-grades')
        self.assertEqual(url, '/grades/assign/')

    def test_student_grades_url(self):
        url = reverse('grades:student-grades')
        self.assertEqual(url, '/grades/student/')

    def test_reports_url(self):
        url = reverse('grades:reports')
        self.assertEqual(url, '/grades/reports/')


class GradeDashboardViewTest(TestCase):
    """Test the grade dashboard view"""

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
        response = self.client.get(reverse('grades:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('grades:dashboard'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_dashboard_accessible_by_teacher(self):
        self.client.login(email='teacher@test.com', password='pass123')
        response = self.client.get(reverse('grades:dashboard'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_dashboard_accessible_by_student(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.get(reverse('grades:dashboard'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login


class AssignGradesViewTest(TestCase):
    """Test the assign grades view access control"""

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

    def test_assign_requires_login(self):
        response = self.client.get(reverse('grades:assign-grades'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_assign_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('grades:assign-grades'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_assign_accessible_by_teacher(self):
        self.client.login(email='teacher@test.com', password='pass123')
        response = self.client.get(reverse('grades:assign-grades'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_assign_blocked_for_student(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.get(reverse('grades:assign-grades'))
        self.assertEqual(response.status_code, 302)


class StudentGradeViewTest(TestCase):
    """Test the student grades view access control"""

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )
        self.teacher = User.objects.create_user(
            email='teacher@test.com', password='pass123', role='teacher'
        )

    def test_student_grades_requires_login(self):
        response = self.client.get(reverse('grades:student-grades'))
        self.assertEqual(response.status_code, 302)

    def test_student_grades_accessible_by_student(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.get(reverse('grades:student-grades'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_student_grades_blocked_for_teacher(self):
        self.client.login(email='teacher@test.com', password='pass123')
        response = self.client.get(reverse('grades:student-grades'))
        self.assertEqual(response.status_code, 302)


class GradeReportsViewTest(TestCase):
    """Test grade reports view access control"""

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
        response = self.client.get(reverse('grades:reports'))
        self.assertEqual(response.status_code, 302)

    def test_reports_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('grades:reports'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_reports_blocked_for_student(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.get(reverse('grades:reports'))
        self.assertEqual(response.status_code, 302)
