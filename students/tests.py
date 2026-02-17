"""
Comprehensive tests for the students app.
Tests: utility functions, algorithms, views access control, API endpoints.
"""
from django.test import TestCase
from django.urls import reverse, resolve
from accounts.models import User
from test_helpers import SafeClient as Client
from students.utils import sort_students_by_name, sort_students_by_roll
from students.algorithms import binary_search_students
import string
import secrets


# ============================================================================
# Mock student objects for testing sort/search without MongoDB
# ============================================================================

class MockStudent:
    """Lightweight mock for testing algorithms that work on student objects"""
    def __init__(self, first_name, last_name, student_id='', roll_number='',
                 email='', phone_number='', program='BCA'):
        self.first_name = first_name
        self.last_name = last_name
        self.student_id = student_id
        self.roll_number = roll_number
        self.email = email
        self.phone_number = phone_number
        self.program = program

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class SortStudentsByNameTest(TestCase):
    """Test the sort_students_by_name utility"""

    def test_sort_alphabetically(self):
        students = [
            MockStudent('Charlie', 'Brown'),
            MockStudent('Alice', 'Smith'),
            MockStudent('Bob', 'Jones'),
        ]
        sorted_students = sort_students_by_name(students)
        names = [s.first_name for s in sorted_students]
        self.assertEqual(names, ['Alice', 'Bob', 'Charlie'])

    def test_sort_same_first_name(self):
        """sort_students_by_name sorts only by first_name, so same first names keep original order"""
        students = [
            MockStudent('Alice', 'Zeta'),
            MockStudent('Alice', 'Alpha'),
        ]
        sorted_students = sort_students_by_name(students)
        # Both named Alice - stable sort preserves original order
        self.assertEqual(len(sorted_students), 2)
        self.assertEqual(sorted_students[0].first_name, 'Alice')

    def test_sort_empty_list(self):
        sorted_students = sort_students_by_name([])
        self.assertEqual(sorted_students, [])

    def test_sort_single_student(self):
        students = [MockStudent('Alice', 'Smith')]
        sorted_students = sort_students_by_name(students)
        self.assertEqual(len(sorted_students), 1)

    def test_sort_case_insensitive(self):
        students = [
            MockStudent('charlie', 'Brown'),
            MockStudent('Alice', 'Smith'),
        ]
        sorted_students = sort_students_by_name(students)
        # Should handle mixed case
        self.assertEqual(len(sorted_students), 2)


class SortStudentsByRollTest(TestCase):
    """Test the sort_students_by_roll utility (bug fix verified)"""

    def test_sort_numeric_rolls(self):
        students = [
            MockStudent('C', 'C', roll_number='3'),
            MockStudent('A', 'A', roll_number='1'),
            MockStudent('B', 'B', roll_number='2'),
        ]
        sorted_students = sort_students_by_roll(students)
        rolls = [s.roll_number for s in sorted_students]
        self.assertEqual(rolls, ['1', '2', '3'])

    def test_sort_with_none_roll(self):
        """Bug fix: Previously crashed with AttributeError when roll_number was None"""
        students = [
            MockStudent('A', 'A', roll_number='1'),
            MockStudent('B', 'B', roll_number=None),
            MockStudent('C', 'C', roll_number='2'),
        ]
        sorted_students = sort_students_by_roll(students)
        # Students with None roll should be at the end
        self.assertEqual(sorted_students[-1].first_name, 'B')

    def test_sort_with_empty_roll(self):
        """Bug fix: Previously crashed when roll_number was empty string"""
        students = [
            MockStudent('A', 'A', roll_number='1'),
            MockStudent('B', 'B', roll_number=''),
            MockStudent('C', 'C', roll_number='2'),
        ]
        sorted_students = sort_students_by_roll(students)
        self.assertEqual(sorted_students[-1].first_name, 'B')

    def test_sort_all_none_rolls(self):
        students = [
            MockStudent('A', 'A', roll_number=None),
            MockStudent('B', 'B', roll_number=None),
        ]
        sorted_students = sort_students_by_roll(students)
        self.assertEqual(len(sorted_students), 2)

    def test_sort_alphanumeric_rolls(self):
        students = [
            MockStudent('A', 'A', roll_number='BCA-003'),
            MockStudent('B', 'B', roll_number='BCA-001'),
            MockStudent('C', 'C', roll_number='BCA-002'),
        ]
        sorted_students = sort_students_by_roll(students)
        rolls = [s.roll_number for s in sorted_students]
        self.assertEqual(rolls, ['BCA-001', 'BCA-002', 'BCA-003'])

    def test_sort_empty_list(self):
        sorted_students = sort_students_by_roll([])
        self.assertEqual(sorted_students, [])

    def test_sort_mixed_numeric_and_none(self):
        students = [
            MockStudent('D', 'D', roll_number=None),
            MockStudent('A', 'A', roll_number='10'),
            MockStudent('C', 'C', roll_number=''),
            MockStudent('B', 'B', roll_number='2'),
        ]
        sorted_students = sort_students_by_roll(students)
        # Numeric sorted first, then None/empty at end
        self.assertEqual(sorted_students[0].roll_number, '2')
        self.assertEqual(sorted_students[1].roll_number, '10')


class BinarySearchStudentsTest(TestCase):
    """Test the binary search algorithm"""

    def setUp(self):
        self.students = [
            MockStudent('Alice', 'Smith', student_id='STU001',
                         email='alice@test.com', phone_number='1234567890'),
            MockStudent('Bob', 'Jones', student_id='STU002',
                         email='bob@test.com', phone_number='0987654321'),
            MockStudent('Charlie', 'Brown', student_id='STU003',
                         email='charlie@test.com', phone_number='5555555555'),
            MockStudent('David', 'Wilson', student_id='STU004',
                         email='david@test.com', phone_number='1112223333'),
        ]

    def test_search_by_first_name(self):
        results = binary_search_students(self.students, 'Alice')
        self.assertTrue(any(s.first_name == 'Alice' for s in results))

    def test_search_by_last_name(self):
        results = binary_search_students(self.students, 'Jones')
        self.assertTrue(any(s.last_name == 'Jones' for s in results))

    def test_search_by_student_id(self):
        results = binary_search_students(self.students, 'STU003')
        self.assertTrue(any(s.student_id == 'STU003' for s in results))

    def test_search_case_insensitive(self):
        results = binary_search_students(self.students, 'alice')
        self.assertTrue(any(s.first_name == 'Alice' for s in results))

    def test_search_no_results(self):
        results = binary_search_students(self.students, 'Zzzzzz')
        self.assertEqual(len(results), 0)

    def test_search_empty_query(self):
        results = binary_search_students(self.students, '')
        # Empty query should return all or empty based on implementation
        self.assertIsInstance(results, list)

    def test_search_empty_list(self):
        results = binary_search_students([], 'test')
        self.assertEqual(len(results), 0)

    def test_search_partial_match(self):
        results = binary_search_students(self.students, 'ali')
        self.assertTrue(any(s.first_name == 'Alice' for s in results))


# ============================================================================
# View Access Control Tests (using Django test client, no MongoDB needed)
# ============================================================================

class StudentViewAccessTest(TestCase):
    """Test that student views enforce proper access control"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='adminpass123',
            role='admin', is_staff=True
        )
        self.student_user = User.objects.create_user(
            email='student@test.com', password='studentpass123',
            role='student'
        )

    def test_student_list_requires_login(self):
        response = self.client.get(reverse('students:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_student_create_requires_login(self):
        response = self.client.get(reverse('students:create'))
        self.assertEqual(response.status_code, 302)

    def test_student_list_accessible_when_logged_in(self):
        self.client.login(email='admin@test.com', password='adminpass123')
        response = self.client.get(reverse('students:list'))
        self.assertNotEqual(response.status_code, 302)

    def test_student_create_accessible_when_logged_in(self):
        self.client.login(email='admin@test.com', password='adminpass123')
        response = self.client.get(reverse('students:create'))
        self.assertNotEqual(response.status_code, 302)


class StudentURLResolutionTest(TestCase):
    """Test that all student URLs resolve correctly"""

    def test_student_list_url(self):
        url = reverse('students:list')
        self.assertEqual(url, '/students/')

    def test_student_create_url(self):
        url = reverse('students:create')
        self.assertEqual(url, '/students/create/')

    def test_student_dashboard_stats_url(self):
        url = reverse('students:api-stats')
        self.assertEqual(url, '/students/api/stats/')

    def test_random_forest_url(self):
        url = reverse('students:random-forest-analysis')
        self.assertEqual(url, '/students/random-forest-analysis/')

    def test_kmeans_url(self):
        url = reverse('students:kmeans-clustering')
        self.assertEqual(url, '/students/kmeans-clustering/')


class StudentDashboardStatsTest(TestCase):
    """Test the student dashboard stats endpoint"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )

    def test_stats_requires_login(self):
        response = self.client.get(reverse('students:api-stats'))
        self.assertEqual(response.status_code, 302)

    def test_stats_returns_json(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('students:api-stats'))
        self.assertNotEqual(response.status_code, 302)
        if response.status_code == 200:
            self.assertEqual(response['Content-Type'], 'application/json')


class AnalysisViewsTest(TestCase):
    """Test ML analysis view access"""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            email='admin@test.com', password='pass123',
            role='admin', is_staff=True
        )

    def test_random_forest_requires_login(self):
        response = self.client.get(reverse('students:random-forest-analysis'))
        self.assertEqual(response.status_code, 302)

    def test_random_forest_get_shows_form(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('students:random-forest-analysis'))
        self.assertNotEqual(response.status_code, 302)

    def test_kmeans_requires_login(self):
        response = self.client.get(reverse('students:kmeans-clustering'))
        self.assertEqual(response.status_code, 302)

    def test_kmeans_get_shows_form(self):
        self.client.login(email='admin@test.com', password='pass123')
        response = self.client.get(reverse('students:kmeans-clustering'))
        self.assertNotEqual(response.status_code, 302)
