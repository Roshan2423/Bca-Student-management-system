"""
Comprehensive tests for the accounts app.
Tests: User model, login/logout, profile views, password management, API endpoints.
"""
from django.test import TestCase
from django.urls import reverse
from accounts.models import User, UserProfile
from accounts.views import generate_random_password
from test_helpers import SafeClient as Client
import string


class UserModelTest(TestCase):
    """Test the custom User model"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            role='student'
        )

    def test_create_user(self):
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertEqual(self.user.role, 'student')
        self.assertTrue(self.user.is_active)
        self.assertFalse(self.user.is_staff)

    def test_create_user_no_email_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email='', password='test')

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertEqual(admin.role, 'admin')

    def test_full_name_property(self):
        self.assertEqual(self.user.full_name, 'Test User')

    def test_full_name_empty(self):
        user = User.objects.create_user(
            email='empty@example.com', password='test123'
        )
        self.assertEqual(user.full_name, '')

    def test_str_representation(self):
        self.assertEqual(str(self.user), 'test@example.com')

    def test_email_normalized(self):
        user = User.objects.create_user(
            email='Test2@EXAMPLE.com', password='test123'
        )
        self.assertEqual(user.email, 'Test2@example.com')

    def test_password_is_hashed(self):
        self.assertNotEqual(self.user.password, 'testpass123')
        self.assertTrue(self.user.check_password('testpass123'))

    def test_role_choices(self):
        for role in ['admin', 'teacher', 'student']:
            user = User.objects.create_user(
                email=f'{role}@example.com', password='test123', role=role
            )
            self.assertEqual(user.role, role)


class GenerateRandomPasswordTest(TestCase):
    """Test the password generation function"""

    def test_default_length(self):
        password = generate_random_password()
        self.assertEqual(len(password), 10)

    def test_custom_length(self):
        password = generate_random_password(length=16)
        self.assertEqual(len(password), 16)

    def test_contains_uppercase(self):
        # Run multiple times to ensure it's not a fluke
        for _ in range(10):
            password = generate_random_password()
            has_upper = any(c in string.ascii_uppercase for c in password)
            self.assertTrue(has_upper, f"Password '{password}' has no uppercase letter")

    def test_contains_lowercase(self):
        for _ in range(10):
            password = generate_random_password()
            has_lower = any(c in string.ascii_lowercase for c in password)
            self.assertTrue(has_lower, f"Password '{password}' has no lowercase letter")

    def test_contains_digit(self):
        for _ in range(10):
            password = generate_random_password()
            has_digit = any(c in string.digits for c in password)
            self.assertTrue(has_digit, f"Password '{password}' has no digit")

    def test_unique_passwords(self):
        passwords = {generate_random_password() for _ in range(20)}
        self.assertGreater(len(passwords), 15, "Too many duplicate passwords generated")


class LoginViewTest(TestCase):
    """Test the login flow"""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('accounts:login')
        self.user = User.objects.create_user(
            email='student@test.com',
            password='studentpass123',
            first_name='Test',
            last_name='Student',
            role='student'
        )
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
            role='admin',
            is_staff=True
        )
        self.teacher = User.objects.create_user(
            email='teacher@test.com',
            password='teacherpass123',
            first_name='Teacher',
            last_name='User',
            role='teacher'
        )

    def test_login_page_loads(self):
        response = self.client.get(self.login_url)
        self.assertNotEqual(response.status_code, 302)  # Not redirect

    def test_login_with_valid_credentials(self):
        response = self.client.post(self.login_url, {
            'username': 'student@test.com',
            'password': 'studentpass123',
        })
        # Should redirect on successful login
        self.assertEqual(response.status_code, 302)

    def test_login_with_invalid_password(self):
        response = self.client.post(self.login_url, {
            'username': 'student@test.com',
            'password': 'wrongpassword',
        })
        self.assertNotEqual(response.status_code, 302)  # stays on login page

    def test_login_with_nonexistent_user(self):
        response = self.client.post(self.login_url, {
            'username': 'nobody@test.com',
            'password': 'testpass123',
        })
        self.assertNotEqual(response.status_code, 302)  # stays on login page

    def test_login_inactive_user_rejected(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.login_url, {
            'username': 'student@test.com',
            'password': 'studentpass123',
        })
        self.assertNotEqual(response.status_code, 302)  # stays on login page

    def test_admin_redirect_after_login(self):
        response = self.client.post(self.login_url, {
            'username': 'admin@test.com',
            'password': 'adminpass123',
        }, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('admin', response.url)

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(email='student@test.com', password='studentpass123')
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)


class LogoutViewTest(TestCase):
    """Test the logout flow"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@test.com', password='testpass123', role='student'
        )
        self.client.login(email='user@test.com', password='testpass123')

    def test_logout_redirects_to_login(self):
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_session_cleared_after_logout(self):
        self.client.post(reverse('accounts:logout'))
        response = self.client.get(reverse('accounts:profile'))
        # Should redirect to login since logged out
        self.assertEqual(response.status_code, 302)


class ProfileViewTest(TestCase):
    """Test profile views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@test.com', password='testpass123',
            first_name='Test', last_name='User', role='student'
        )
        self.admin = User.objects.create_user(
            email='admin@test.com', password='adminpass123',
            first_name='Admin', last_name='User', role='admin'
        )

    def test_profile_requires_login(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)

    def test_profile_loads_for_authenticated_user(self):
        self.client.login(email='user@test.com', password='testpass123')
        response = self.client.get(reverse('accounts:profile'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_profile_edit_requires_admin(self):
        self.client.login(email='user@test.com', password='testpass123')
        response = self.client.get(reverse('accounts:profile-edit'))
        self.assertEqual(response.status_code, 302)  # redirected

    def test_profile_edit_accessible_by_admin(self):
        self.client.login(email='admin@test.com', password='adminpass123')
        response = self.client.get(reverse('accounts:profile-edit'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected


class ChangeOwnPasswordTest(TestCase):
    """Test users changing their own password"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='user@test.com', password='oldpass123', role='student'
        )
        self.client.login(email='user@test.com', password='oldpass123')

    def test_change_password_success(self):
        response = self.client.post(reverse('accounts:change-own-password'), {
            'current_password': 'oldpass123',
            'new_password': 'newpass1234',
            'confirm_password': 'newpass1234',
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass1234'))

    def test_change_password_wrong_current(self):
        response = self.client.post(reverse('accounts:change-own-password'), {
            'current_password': 'wrongpass',
            'new_password': 'newpass1234',
            'confirm_password': 'newpass1234',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpass123'))

    def test_change_password_mismatch(self):
        response = self.client.post(reverse('accounts:change-own-password'), {
            'current_password': 'oldpass123',
            'new_password': 'newpass1234',
            'confirm_password': 'different123',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpass123'))

    def test_change_password_too_short(self):
        response = self.client.post(reverse('accounts:change-own-password'), {
            'current_password': 'oldpass123',
            'new_password': 'short',
            'confirm_password': 'short',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpass123'))


class AdminPasswordManagementTest(TestCase):
    """Test admin password management"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='adminpass123',
            role='admin', is_staff=True
        )
        self.student = User.objects.create_user(
            email='student@test.com', password='studentpass123',
            role='student', first_name='Test', last_name='Student'
        )

    def test_admin_password_page_requires_admin(self):
        self.client.login(email='student@test.com', password='studentpass123')
        response = self.client.get(reverse('accounts:admin-password-management'))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_access_password_page(self):
        self.client.login(email='admin@test.com', password='adminpass123')
        response = self.client.get(reverse('accounts:admin-password-management'))
        self.assertNotEqual(response.status_code, 302)  # Not redirected to login

    def test_admin_set_user_password(self):
        self.client.login(email='admin@test.com', password='adminpass123')
        response = self.client.post(
            reverse('accounts:change-user-password', args=[self.student.id]),
            {
                'action': 'set_password',
                'new_password': 'newstudentpw1',
                'confirm_password': 'newstudentpw1',
            }
        )
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password('newstudentpw1'))

    def test_admin_generate_password(self):
        self.client.login(email='admin@test.com', password='adminpass123')
        response = self.client.post(
            reverse('accounts:change-user-password', args=[self.student.id]),
            {'action': 'generate_password'}
        )
        self.student.refresh_from_db()
        # Password should have changed from the original
        self.assertFalse(self.student.check_password('studentpass123'))


class DashboardRoutingTest(TestCase):
    """Test role-based dashboard routing"""

    def setUp(self):
        self.client = Client()

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_admin_routed_to_admin_dashboard(self):
        admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('admin', response.url)


class APIViewsTest(TestCase):
    """Test REST API views"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True, first_name='Admin', last_name='User'
        )
        self.student_user = User.objects.create_user(
            email='student@test.com', password='pass123',
            role='student', first_name='Student', last_name='User'
        )

    def test_current_user_requires_auth(self):
        response = self.client.get(reverse('accounts:current-user'))
        self.assertIn(response.status_code, [401, 403])

    def test_current_user_returns_data(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('accounts:current-user'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'admin@test.com')

    def test_user_list_requires_admin(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.get('/accounts/api/users/')
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_users(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get('/accounts/api/users/')
        self.assertEqual(response.status_code, 200)

    def test_api_change_password(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.post(
            reverse('accounts:api-change-password'),
            {'old_password': 'pass123', 'new_password': 'newpass1234'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.student_user.refresh_from_db()
        self.assertTrue(self.student_user.check_password('newpass1234'))

    def test_api_change_password_wrong_old(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.post(
            reverse('accounts:api-change-password'),
            {'old_password': 'wrong', 'new_password': 'newpass1234'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

    def test_api_change_password_too_short(self):
        self.client.login(email='student@test.com', password='pass123')
        response = self.client.post(
            reverse('accounts:api-change-password'),
            {'old_password': 'pass123', 'new_password': 'short'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
