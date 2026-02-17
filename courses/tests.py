"""
Comprehensive tests for the courses app.
Tests: URL resolution, view access control, serializer imports.
"""
from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from test_helpers import SafeClient as Client


class CourseURLResolutionTest(TestCase):
    """Test that all course URLs resolve correctly"""

    def test_course_management_url(self):
        url = reverse('courses:course-management')
        self.assertEqual(url, '/courses/management/')

    def test_teacher_list_url(self):
        url = reverse('courses:teacher-list')
        self.assertEqual(url, '/courses/teachers/')

    def test_teacher_create_url(self):
        url = reverse('courses:teacher-create')
        self.assertEqual(url, '/courses/teacher/create/')

    def test_fee_management_url(self):
        url = reverse('courses:fee-management')
        self.assertEqual(url, '/courses/fees/')

    def test_salary_management_url(self):
        url = reverse('courses:salary-management')
        self.assertEqual(url, '/courses/salaries/')


class SerializerImportTest(TestCase):
    """Test that course serializers import without errors (bug fix verified)"""

    def test_serializer_imports(self):
        """Bug fix: Previously imported non-existent Course and Enrollment models"""
        from courses.serializers import TeacherSerializer, CourseSerializer, EnrollmentSerializer
        self.assertTrue(TeacherSerializer is not None)
        self.assertTrue(CourseSerializer is not None)
        self.assertTrue(EnrollmentSerializer is not None)


class CourseManagementViewTest(TestCase):
    """Test course management view"""

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

    def test_course_management_requires_login(self):
        response = self.client.get(reverse('courses:course-management'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_course_management_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('courses:course-management'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_course_management_accessible_by_teacher(self):
        self.client.login(email='teacher@test.com', password='pass123')
        response = self.client.get(reverse('courses:course-management'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login


class TeacherManagementViewTest(TestCase):
    """Test teacher management views"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )

    def test_teacher_list_requires_login(self):
        response = self.client.get(reverse('courses:teacher-list'))
        self.assertEqual(response.status_code, 302)

    def test_teacher_list_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('courses:teacher-list'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_teacher_create_requires_login(self):
        response = self.client.get(reverse('courses:teacher-create'))
        self.assertEqual(response.status_code, 302)

    def test_teacher_create_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('courses:teacher-create'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login


class StudentDashboardViewTest(TestCase):
    """Test student dashboard view"""

    def setUp(self):
        self.client = Client()
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )

    def test_student_dashboard_requires_login(self):
        response = self.client.get(reverse('courses:student-dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_student_dashboard_accessible_by_student(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.get(reverse('courses:student-dashboard'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login


class FeeManagementViewTest(TestCase):
    """Test fee management views"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )
        self.student = User.objects.create_user(
            email='student@test.com', password='pass123', role='student'
        )

    def test_fee_management_requires_login(self):
        response = self.client.get(reverse('courses:fee-management'))
        self.assertEqual(response.status_code, 302)

    def test_fee_management_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('courses:fee-management'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login


class SalaryManagementViewTest(TestCase):
    """Test salary management views"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )

    def test_salary_management_requires_login(self):
        response = self.client.get(reverse('courses:salary-management'))
        self.assertEqual(response.status_code, 302)

    def test_salary_management_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('courses:salary-management'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login
