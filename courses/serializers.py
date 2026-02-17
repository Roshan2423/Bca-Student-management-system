# Create/Replace courses/serializers.py with this content:

from rest_framework import serializers
from .models import BCASubject, Teacher, StudentEnrollment
import datetime


class TeacherSerializer(serializers.Serializer):
    """Serializer for Teacher model"""
    id = serializers.CharField(read_only=True)
    teacher_id = serializers.CharField(max_length=20)
    department = serializers.CharField(max_length=100)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    highest_qualification = serializers.ChoiceField(
        choices=['bachelor', 'master', 'phd', 'diploma'],
        required=False,
        allow_blank=True
    )
    specialization = serializers.CharField(max_length=200, required=False, allow_blank=True)
    experience_years = serializers.IntegerField(default=0)
    employment_type = serializers.ChoiceField(
        choices=['full_time', 'part_time', 'contract', 'visiting'],
        default='full_time'
    )
    office_phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    office_address = serializers.CharField(required=False, allow_blank=True)
    join_date = serializers.DateTimeField()
    salary = serializers.FloatField(required=False, allow_null=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(default=True)
    
    # Read-only computed fields
    full_name = serializers.CharField(read_only=True)
    email = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class CourseSerializer(serializers.Serializer):
    """Serializer for Course model"""
    id = serializers.CharField(read_only=True)
    course_code = serializers.CharField(max_length=20)
    course_name = serializers.CharField(max_length=200)
    course_description = serializers.CharField(required=False, allow_blank=True)
    credits = serializers.IntegerField(default=3)
    course_type = serializers.ChoiceField(
        choices=['core', 'elective', 'practical', 'project'],
        default='core'
    )
    semester = serializers.ChoiceField(
        choices=[('1', 'First'), ('2', 'Second'), ('3', 'Third'), ('4', 'Fourth'),
                ('5', 'Fifth'), ('6', 'Sixth'), ('7', 'Seventh'), ('8', 'Eighth')]
    )
    program = serializers.CharField(max_length=100)
    teacher = serializers.CharField()  # Teacher ID reference
    classroom = serializers.CharField(max_length=50, required=False, allow_blank=True)
    max_students = serializers.IntegerField(default=50)
    syllabus = serializers.CharField(required=False, allow_blank=True)
    theory_marks = serializers.IntegerField(default=70)
    practical_marks = serializers.IntegerField(default=30)
    internal_marks = serializers.IntegerField(default=40)
    external_marks = serializers.IntegerField(default=60)
    is_active = serializers.BooleanField(default=True)
    academic_year = serializers.CharField(max_length=20, default='2024-25')
    
    # Read-only computed fields
    total_marks = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class EnrollmentSerializer(serializers.Serializer):
    """Serializer for Enrollment model"""
    id = serializers.CharField(read_only=True)
    student = serializers.CharField()  # Student ID reference
    course = serializers.CharField()   # Course ID reference
    enrollment_date = serializers.DateTimeField(default=datetime.datetime.now)
    status = serializers.ChoiceField(
        choices=['enrolled', 'dropped', 'completed', 'failed'],
        default='enrolled'
    )
    academic_year = serializers.CharField(max_length=20)
    
    # Grade information
    internal_marks = serializers.FloatField(default=0.0)
    external_marks = serializers.FloatField(default=0.0)
    practical_marks = serializers.FloatField(default=0.0)
    total_marks = serializers.FloatField(read_only=True)
    grade = serializers.CharField(max_length=2, read_only=True)
    grade_points = serializers.FloatField(read_only=True)
    
    # Additional information
    attendance_percentage = serializers.FloatField(default=0.0)
    is_retake = serializers.BooleanField(default=False)
    drop_date = serializers.DateTimeField(required=False, allow_null=True)
    completion_date = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    
    # Read-only fields
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)