# Replace your students/models.py with this fixed version:

from mongoengine import Document, StringField, EmailField, DateTimeField, ReferenceField, ListField, FloatField, IntField, BooleanField, DateField
from accounts.models import UserProfile
import datetime

class Student(Document):
    """Student model with correct field names to match the form"""
    
    SEMESTER_CHOICES = [
        (1, '1st Semester'),
        (2, '2nd Semester'), 
        (3, '3rd Semester'),
        (4, '4th Semester'),
        (5, '5th Semester'),
        (6, '6th Semester'),
        (7, '7th Semester'),
        (8, '8th Semester'),
    ]
    
    PROGRAM_CHOICES = [
        ('BCA', 'Bachelor of Computer Applications'),
        ('BIT', 'Bachelor of Information Technology'),
        ('MBA', 'Master of Business Administration'),
        ('MCA', 'Master of Computer Applications'),
    ]
    
    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]
    
    # Basic Information - FIXED FIELD NAMES
    student_id = StringField(max_length=50, required=True, unique=True)
    first_name = StringField(max_length=100, required=True)  # Fixed: was fname
    last_name = StringField(max_length=100, required=True)   # Fixed: was lname
    email = EmailField(required=True, unique=True)           # Fixed: was email_address
    phone_number = StringField(max_length=20)               # Fixed: was phone
    date_of_birth = DateField()                              # Fixed: was birth_date
    gender = StringField(max_length=10, choices=GENDER_CHOICES)  # Fixed: was sex
    address = StringField()                                  # Fixed: was home_address
    
    # Academic Information
    program = StringField(max_length=10, choices=PROGRAM_CHOICES, required=True)
    current_semester = IntField(choices=SEMESTER_CHOICES, required=True)
    admission_date = DateField(required=True)
    batch = StringField(max_length=20)
    roll_number = StringField(max_length=20)
    
    # Emergency Contact
    emergency_contact_name = StringField(max_length=100)
    emergency_contact_phone = StringField(max_length=20)
    
    # Additional Information
    notes = StringField()
    is_active = BooleanField(default=True)
    
    # Timestamps
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)
    
    meta = {
        'collection': 'students',
        'indexes': [
            'student_id',
            'email',
            'program',
            'current_semester',
            'is_active'
        ]
    }
    
    def save(self, *args, **kwargs):
        """Override save to update timestamp and sync enrollment"""
        self.updated_at = datetime.datetime.now()
        result = super().save(*args, **kwargs)
        
        # Sync StudentEnrollment when student's semester changes
        self.sync_enrollment()
        
        return result
    
    def sync_enrollment(self):
        """Ensure StudentEnrollment is synced with this student's current_semester"""
        from courses.models import StudentEnrollment
        
        enrollment = StudentEnrollment.objects.filter(student=self).first()
        if enrollment and enrollment.current_semester != self.current_semester:
            print(f"DEBUG: Auto-syncing enrollment for {self.full_name}: {enrollment.current_semester} -> {self.current_semester}")
            enrollment.current_semester = self.current_semester
            enrollment.save()
        elif not enrollment:
            # Create enrollment if it doesn't exist
            enrollment = StudentEnrollment(
                student=self,
                current_semester=self.current_semester
            )
            enrollment.save()
            print(f"DEBUG: Created new enrollment for {self.full_name} in semester {self.current_semester}")
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_id})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def semester_display(self):
        return f"{self.current_semester} Semester"
    
    @property
    def program_display(self):
        return dict(self.PROGRAM_CHOICES).get(self.program, self.program)


class StudentDocument(Document):
    """Document storage for students"""
    
    DOCUMENT_TYPES = [
        ('transcript', 'Academic Transcript'),
        ('certificate', 'Certificate'),
        ('id_copy', 'ID Copy'),
        ('photo', 'Photograph'),
        ('other', 'Other'),
    ]
    
    student = ReferenceField(Student, required=True)
    document_type = StringField(max_length=20, choices=DOCUMENT_TYPES, required=True)
    title = StringField(max_length=200, required=True)
    description = StringField()
    file_path = StringField(max_length=500, required=True)
    uploaded_at = DateTimeField(default=datetime.datetime.now)
    file_size = IntField()  # in bytes
    is_verified = BooleanField(default=False)
    
    meta = {
        'collection': 'student_documents',
        'indexes': [
            'student',
            'document_type',
            'uploaded_at'
        ]
    }
    
    def __str__(self):
        return f"{self.title} - {self.student.full_name}"