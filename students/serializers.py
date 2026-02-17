 
# Replace the content of students/serializers.py with this:

from rest_framework import serializers
from .models import Student, StudentDocument
import datetime


class StudentSerializer(serializers.Serializer):
    """Serializer for Student model"""
    
    id = serializers.CharField(read_only=True)
    student_id = serializers.CharField(max_length=50)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(
        choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')],
        required=False,
        allow_blank=True
    )
    address = serializers.CharField(required=False, allow_blank=True)
    
    # Academic Information
    program = serializers.ChoiceField(
        choices=[
            ('BCA', 'Bachelor of Computer Applications'),
            ('BIT', 'Bachelor of Information Technology'),
            ('MBA', 'Master of Business Administration'),
            ('MCA', 'Master of Computer Applications'),
        ]
    )
    current_semester = serializers.IntegerField(min_value=1, max_value=8)
    admission_date = serializers.DateField()
    batch = serializers.CharField(max_length=20, required=False, allow_blank=True)
    roll_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    
    # Emergency Contact
    emergency_contact_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    
    # Additional fields
    is_active = serializers.BooleanField(default=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    
    def validate_email(self, value):
        """Validate email uniqueness"""
        # For MongoEngine, we need to check manually
        try:
            existing = Student.objects.get(email=value)
            if self.instance and str(existing.id) == str(self.instance.id):
                return value  # Same student, allow
            raise serializers.ValidationError("A student with this email already exists.")
        except Student.DoesNotExist:
            return value
    
    def validate_student_id(self, value):
        """Validate student ID uniqueness"""
        try:
            existing = Student.objects.get(student_id=value)
            if self.instance and str(existing.id) == str(self.instance.id):
                return value  # Same student, allow
            raise serializers.ValidationError("A student with this ID already exists.")
        except Student.DoesNotExist:
            return value
    
    def validate_admission_date(self, value):
        """Validate admission date is not in the future"""
        if value > datetime.date.today():
            raise serializers.ValidationError("Admission date cannot be in the future.")
        return value
    
    def validate_date_of_birth(self, value):
        """Validate date of birth"""
        if value and value > datetime.date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        if value and value < datetime.date(1900, 1, 1):
            raise serializers.ValidationError("Please enter a valid date of birth.")
        return value


class StudentDocumentSerializer(serializers.Serializer):
    """Serializer for StudentDocument model"""
    
    id = serializers.CharField(read_only=True)
    student = serializers.CharField()  # Student ID reference
    document_type = serializers.ChoiceField(
        choices=[
            ('transcript', 'Academic Transcript'),
            ('certificate', 'Certificate'),
            ('id_copy', 'ID Copy'),
            ('photo', 'Photograph'),
            ('other', 'Other'),
        ]
    )
    title = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True)
    file_path = serializers.CharField(max_length=500)
    uploaded_at = serializers.DateTimeField(read_only=True)
    file_size = serializers.IntegerField(required=False)
    is_verified = serializers.BooleanField(default=False)
    
    def validate_student(self, value):
        """Validate student exists"""
        try:
            Student.objects.get(id=value)
            return value
        except Student.DoesNotExist:
            raise serializers.ValidationError("Student not found.")


class StudentListSerializer(serializers.Serializer):
    """Lightweight serializer for student lists"""
    
    id = serializers.CharField(read_only=True)
    student_id = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    program = serializers.CharField()
    current_semester = serializers.IntegerField()
    is_active = serializers.BooleanField()
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class StudentStatsSerializer(serializers.Serializer):
    """Serializer for student statistics"""
    
    total_students = serializers.IntegerField()
    active_students = serializers.IntegerField()
    inactive_students = serializers.IntegerField()
    programs = serializers.DictField()
    semesters = serializers.DictField()


class StudentSearchSerializer(serializers.Serializer):
    """Serializer for student search parameters"""
    
    search = serializers.CharField(required=False, allow_blank=True)
    program = serializers.ChoiceField(
        choices=[
            ('', 'All Programs'),
            ('BCA', 'BCA'),
            ('BIT', 'BIT'),
            ('MBA', 'MBA'),
            ('MCA', 'MCA'),
        ],
        required=False,
        allow_blank=True
    )
    semester = serializers.ChoiceField(
        choices=[('', 'All Semesters')] + [(str(i), f'{i} Semester') for i in range(1, 9)],
        required=False,
        allow_blank=True
    )
    is_active = serializers.BooleanField(required=False)