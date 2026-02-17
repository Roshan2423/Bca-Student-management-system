# Complete updated courses/models.py

from mongoengine import Document, StringField, EmailField, DateTimeField, ReferenceField, ListField, FloatField, IntField, BooleanField, DateField, FileField
from accounts.models import UserProfile
from django.core.exceptions import ValidationError
from mongoengine import Q
from students.models import Student
import datetime

class Teacher(Document):
    """Complete Teacher model with full profile information"""
    
    # Personal Information
    first_name = StringField(max_length=50, required=True)
    last_name = StringField(max_length=50, required=True)
    email = EmailField(required=True, unique=True)
    phone_number = StringField(max_length=15)
    address = StringField()
    date_of_birth = DateTimeField()
    gender = StringField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    
    # Teacher-specific Information
    teacher_id = StringField(max_length=20, required=True, unique=True)
    department = StringField(max_length=100, required=True)
    designation = StringField(max_length=100, required=True)
    qualification = StringField(max_length=200)  # e.g., "Master's in Computer Science"
    experience_years = IntField(default=0)
    
    # Employment Information
    joining_date = DateTimeField(default=datetime.datetime.now)
    employment_type = StringField(max_length=20, choices=[
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('visiting', 'Visiting Faculty')
    ], default='full_time')
    salary = FloatField()  # Optional
    
    # Emergency Contact
    emergency_contact_name = StringField(max_length=100)
    emergency_contact_phone = StringField(max_length=15)
    emergency_contact_relation = StringField(max_length=50)
    
    # System Fields
    user_profile = ReferenceField(UserProfile)  # Optional link to UserProfile
    subjects_teaching = ListField(StringField())  # List of BCA subject codes
    is_active = BooleanField(default=True)
    notes = StringField()  # Admin notes about teacher
    
    # Timestamps
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)
    
    meta = {
        'collection': 'teachers',
        'indexes': ['teacher_id', 'email', 'department']
    }
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.teacher_id})"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super().save(*args, **kwargs)
    
    def get_assigned_subjects(self):
        """Get BCASubject objects assigned to this teacher"""
        return BCASubject.objects.filter(assigned_teacher=self)
    
    def create_user_account(self, password=None):
        """Create Django User and UserProfile for this teacher"""
        from django.contrib.auth import get_user_model
        from django.utils.crypto import get_random_string
        
        User = get_user_model()
        
        # Create Django User
        if not password:
            password = get_random_string(12)  # Generate random password
        
        django_user = User.objects.create_user(
            email=self.email,
            password=password,
            first_name=self.first_name,
            last_name=self.last_name,
            role='teacher'
        )
        
        # Create UserProfile
        user_profile = UserProfile(
            user_id=str(django_user.id),
            email=self.email,
            first_name=self.first_name,
            last_name=self.last_name,
            phone=self.phone_number,
            address=self.address,
            date_of_birth=self.date_of_birth,
            gender=self.gender[0] if self.gender else None,  # Convert to single letter
            role='teacher'
        )
        user_profile.save()
        
        # Link UserProfile to Teacher
        self.user_profile = user_profile
        self.save()
        
        return django_user, password


class BCASubject(Document):
    """Pre-defined BCA subjects from the textbook"""
    
    SEMESTER_CHOICES = [
        (1, 'First Semester'),
        (2, 'Second Semester'),
        (3, 'Third Semester'),
        (4, 'Fourth Semester'),
        (5, 'Fifth Semester'),
        (6, 'Sixth Semester'),
        (7, 'Seventh Semester'),
        (8, 'Eighth Semester'),
    ]
    
    subject_name = StringField(max_length=200, required=True)
    subject_code = StringField(max_length=20, required=True, unique=True)
    semester = IntField(choices=SEMESTER_CHOICES, required=True)
    description = StringField()
    
    # Teacher assignment
    assigned_teacher = ReferenceField(Teacher)
    
    # Additional fields for compatibility
    course_name = StringField(max_length=200)  # Alias for subject_name
    course_code = StringField(max_length=20)   # Alias for subject_code
    credits = IntField(default=3)
    
    # Timestamps
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)
    
    meta = {
        'collection': 'bca_subjects',
        'indexes': ['semester', 'subject_code']
    }
    
    def __str__(self):
        return f"Sem {self.semester}: {self.subject_name}"
    
    def save(self, *args, **kwargs):
        # Auto-sync alias fields
        if not self.course_name:
            self.course_name = self.subject_name
        if not self.course_code:
            self.course_code = self.subject_code
        return super().save(*args, **kwargs)


class CourseMaterial(Document):
    """PDFs and materials uploaded by teachers"""
    
    MATERIAL_TYPES = [
        ('pdf', 'PDF Document'),
        ('video', 'Video'),
        ('presentation', 'Presentation'),
        ('notes', 'Notes'),
        ('other', 'Other'),
    ]
    
    subject = ReferenceField(BCASubject, required=True)
    title = StringField(max_length=200, required=True)
    description = StringField()
    material_type = StringField(choices=MATERIAL_TYPES, default='pdf')
    
    # File upload
    file_path = StringField(max_length=500)  # Path to uploaded file
    file_name = StringField(max_length=255)
    file_size = IntField()  # Size in bytes
    
    # Uploaded by
    uploaded_by = ReferenceField(Teacher, required=True)
    upload_date = DateTimeField(default=datetime.datetime.now)
    
    # Visibility
    is_active = BooleanField(default=True)
    
    meta = {
        'collection': 'course_materials',
        'indexes': ['subject', 'upload_date']
    }
    
    def __str__(self):
        return f"{self.subject.subject_name}: {self.title}"


class Assignment(Document):
    """Assignments created by teachers"""
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('draft', 'Draft'),
    ]
    
    subject = ReferenceField(BCASubject, required=True)
    title = StringField(max_length=200, required=True)
    description = StringField(required=True)
    instructions = StringField()
    
    # Assignment details
    created_by = ReferenceField(Teacher, required=True)
    created_date = DateTimeField(default=datetime.datetime.now)
    due_date = DateTimeField(required=True)
    
    # Assignment file (optional)
    assignment_file_path = StringField(max_length=500)
    assignment_file_name = StringField(max_length=255)
    
    # Status
    status = StringField(choices=STATUS_CHOICES, default='active')
    
    meta = {
        'collection': 'assignments',
        'indexes': ['subject', 'due_date', 'status']
    }
    
    def __str__(self):
        return f"{self.subject.subject_name}: {self.title}"
    
    @property
    def is_overdue(self):
        return datetime.datetime.now() > self.due_date
    
    @property
    def days_remaining(self):
        if self.is_overdue:
            return 0
        delta = self.due_date - datetime.datetime.now()
        return delta.days


class AssignmentSubmission(Document):
    """Student submissions for assignments"""
    
    SUBMISSION_STATUS = [
        ('submitted', 'Submitted'),
        ('late', 'Late Submission'),
        ('approved', 'Approved'),        # NEW: Approved by teacher
        ('rejected', 'Rejected'),        # NEW: Rejected by teacher
        ('graded', 'Graded'),
        ('returned', 'Returned'),
    ]
    
    assignment = ReferenceField(Assignment, required=True)
    student = ReferenceField('students.Student', required=True)  # Reference to Student model
    
    # Submission details
    submission_date = DateTimeField(default=datetime.datetime.now)
    submission_text = StringField()  # Text submission
    
    # File submission
    submission_file_path = StringField(max_length=500)
    submission_file_name = StringField(max_length=255)
    file_size = IntField()
    
    # Grading and Feedback - UPDATED
    marks_obtained = FloatField(default=0.0)
    feedback = StringField()              # Teacher feedback (for rejections or general comments)
    teacher_comments = StringField()      # NEW: Additional teacher comments
    graded_by = ReferenceField(Teacher)
    graded_date = DateTimeField()
    
    # Approval/Rejection - NEW FIELDS
    reviewed_by = ReferenceField(Teacher)      # Teacher who approved/rejected
    reviewed_date = DateTimeField()            # When it was reviewed
    rejection_reason = StringField()           # Specific reason for rejection
    
    # Status
    status = StringField(choices=SUBMISSION_STATUS, default='submitted')
    is_late = BooleanField(default=False)
    
    meta = {
        'collection': 'assignment_submissions',
        'indexes': ['assignment', 'student', 'submission_date', 'status']
    }
    
    def __str__(self):
        return f"{self.student.full_name}: {self.assignment.title}"
    
    def calculate_status(self):
        """Calculate if submission is late"""
        if self.submission_date > self.assignment.due_date:
            self.is_late = True
            if self.status == 'submitted':
                self.status = 'late'
        else:
            self.is_late = False
            if self.status not in ['approved', 'rejected', 'graded', 'returned']:
                self.status = 'submitted'
    
    # NEW METHODS
    def approve(self, teacher, comments=None):
        """Approve the submission"""
        self.status = 'approved'
        self.reviewed_by = teacher
        self.reviewed_date = datetime.datetime.now()
        if comments:
            self.teacher_comments = comments
        self.save()
    
    def reject(self, teacher, reason, feedback=None):
        """Reject the submission with reason"""
        self.status = 'rejected'
        self.reviewed_by = teacher
        self.reviewed_date = datetime.datetime.now()
        self.rejection_reason = reason
        if feedback:
            self.feedback = feedback
        self.save()
    
    @property
    def status_display(self):
        """Get human-readable status"""
        status_map = {
            'submitted': 'Submitted',
            'late': 'Late Submission',
            'approved': 'Approved',
            'rejected': 'Rejected',
            'graded': 'Graded',
            'returned': 'Returned'
        }
        return status_map.get(self.status, self.status.title())


class StudentEnrollment(Document):
    """Track which semester each student is in"""
    
    student = ReferenceField('students.Student', required=True, unique=True)
    current_semester = IntField(min_value=1, max_value=8, required=True)
    academic_year = StringField(max_length=20, default='2024-25')
    enrollment_date = DateTimeField(default=datetime.datetime.now)
    
    # Additional fields for compatibility with grades app
    course = ReferenceField(BCASubject)  # For compatibility
    status = StringField(max_length=20, default='enrolled')
    
    meta = {
        'collection': 'student_enrollments',
        'indexes': ['student', 'current_semester']
    }
    
    def __str__(self):
        return f"{self.student.full_name}: Semester {self.current_semester}"
    
    def get_accessible_subjects(self):
        """Get subjects student can access (current semester only)"""
        return BCASubject.objects.filter(semester=self.current_semester)


class StudentFeeRecord(Document):
    """Track student fee payments per semester"""
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('overdue', 'Overdue'),
    ]
    
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('online', 'Online Payment'),
        ('cheque', 'Cheque'),
    ]
    
    student = ReferenceField('students.Student', required=True)
    semester = IntField(min_value=1, max_value=8, required=True)
    
    # Fee Details
    total_fee = FloatField(default=50000.0)  # Rs.50,000 per semester
    paid_amount = FloatField(default=0.0)
    remaining_amount = FloatField(default=50000.0)
    
    # Payment Status
    payment_status = StringField(choices=PAYMENT_STATUS, default='pending')
    is_completed = BooleanField(default=False)
    
    # Payment Details
    payment_date = DateTimeField()
    payment_method = StringField(choices=PAYMENT_METHODS)
    receipt_number = StringField()
    bank_reference = StringField()  # For bank transfers
    
    # Administrative
    recorded_by = ReferenceField('accounts.UserProfile')  # Admin who recorded payment
    notes = StringField()
    
    # Timestamps
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)
    
    meta = {
        'collection': 'student_fee_records',
        'indexes': ['student', 'semester', 'payment_status', 'created_at']
    }
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        
        # Calculate remaining amount
        self.remaining_amount = self.total_fee - self.paid_amount
        
        # Update payment status
        if self.paid_amount == 0:
            self.payment_status = 'pending'
            self.is_completed = False
        elif self.paid_amount >= self.total_fee:
            self.payment_status = 'paid'
            self.is_completed = True
            self.remaining_amount = 0.0
        else:
            self.payment_status = 'partial'
            self.is_completed = False
        
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student.full_name} - Semester {self.semester} - Rs.{self.paid_amount}/{self.total_fee}"
    
    @property
    def payment_percentage(self):
        if self.total_fee > 0:
            return round((self.paid_amount / self.total_fee) * 100, 1)
        return 0


class TeacherSalaryRecord(Document):
    """Track teacher monthly salary payments"""
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('advance', 'Advance Given'),
        ('delayed', 'Delayed'),
    ]
    
    PAYMENT_METHODS = [
        ('bank_transfer', 'Bank Transfer'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
    ]
    
    teacher = ReferenceField(Teacher, required=True)
    month = IntField(min_value=1, max_value=12, required=True)
    year = IntField(required=True)
    
    # Salary Details
    base_salary = FloatField(required=True)  # From teacher profile
    bonus = FloatField(default=0.0)
    deductions = FloatField(default=0.0)
    net_salary = FloatField(required=True)
    
    # Payment Status
    payment_status = StringField(choices=PAYMENT_STATUS, default='pending')
    is_paid = BooleanField(default=False)
    
    # Payment Details
    payment_date = DateTimeField()
    payment_method = StringField(choices=PAYMENT_METHODS)
    bank_reference = StringField()
    
    # Administrative
    processed_by = ReferenceField('accounts.UserProfile')  # Admin who processed payment
    notes = StringField()
    
    # Timestamps
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)
    
    meta = {
        'collection': 'teacher_salary_records',
        'indexes': ['teacher', 'month', 'year', 'payment_status', 'created_at'],
        'unique_together': [('teacher', 'month', 'year')]  # One record per teacher per month
    }
    
    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        
        # Calculate net salary
        self.net_salary = self.base_salary + self.bonus - self.deductions
        
        # Update payment status
        if self.payment_date and self.payment_status == 'paid':
            self.is_paid = True
        else:
            self.is_paid = False
        
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.teacher.full_name} - {self.month}/{self.year} - Rs.{self.net_salary}"
    
    @property
    def month_name(self):
        months = [
            '', 'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        return months[self.month] if 1 <= self.month <= 12 else 'Unknown'
    
    @classmethod
    def generate_monthly_records(cls, month, year):
        """Generate monthly salary records for all active teachers"""
        active_teachers = Teacher.objects.filter(is_active=True)
        created_count = 0
        
        for teacher in active_teachers:
            # Check if record already exists
            existing = cls.objects.filter(teacher=teacher, month=month, year=year).first()
            if not existing and teacher.salary:
                salary_record = cls(
                    teacher=teacher,
                    month=month,
                    year=year,
                    base_salary=teacher.salary,
                    net_salary=teacher.salary
                )
                salary_record.save()
                created_count += 1
        
        return created_count


# Pre-populate BCA subjects from your textbook
def populate_bca_subjects():
    """Function to populate all BCA subjects"""
    
    subjects_data = {
        1: [  # First Semester
            {'name': 'Computer Fundamentals and Applications', 'code': 'BCA101'},
            {'name': 'Society & Technology', 'code': 'BCA102'},
            {'name': 'English I', 'code': 'BCA103'},
            {'name': 'Mathematics I', 'code': 'BCA104'},
            {'name': 'Digital Logic', 'code': 'BCA105'},
        ],
        2: [  # Second Semester
            {'name': 'C Programming', 'code': 'BCA201'},
            {'name': 'Financial Accounting', 'code': 'BCA202'},
            {'name': 'English II', 'code': 'BCA203'},
            {'name': 'Mathematics II', 'code': 'BCA204'},
            {'name': 'Microprocessor and Computer Architecture', 'code': 'BCA205'},
        ],
        3: [  # Third Semester
            {'name': 'Data Structure and Algorithms', 'code': 'BCA301'},
            {'name': 'Probability and Statistics', 'code': 'BCA302'},
            {'name': 'System Analysis and Design', 'code': 'BCA303'},
            {'name': 'OOP in Java', 'code': 'BCA304'},
            {'name': 'Web Technology', 'code': 'BCA305'},
        ],
        4: [  # Fourth Semester
            {'name': 'Operating System', 'code': 'BCA401'},
            {'name': 'Numerical Methods', 'code': 'BCA402'},
            {'name': 'Software Engineering', 'code': 'BCA403'},
            {'name': 'Scripting Language', 'code': 'BCA404'},
            {'name': 'Database Management System', 'code': 'BCA405'},
        ],
        5: [  # Fifth Semester
            {'name': 'MIS and e-Business', 'code': 'BCA501'},
            {'name': 'DotNet Technology', 'code': 'BCA502'},
            {'name': 'Computer Networking', 'code': 'BCA503'},
            {'name': 'Introduction to Management', 'code': 'BCA504'},
            {'name': 'Computer Graphics and Animation', 'code': 'BCA505'},
        ],
        6: [  # Sixth Semester
            {'name': 'Mobile Programming', 'code': 'BCA601'},
            {'name': 'Distributed System', 'code': 'BCA602'},
            {'name': 'Applied Economics', 'code': 'BCA603'},
            {'name': 'Advanced Java Programming', 'code': 'BCA604'},
            {'name': 'Network Programming', 'code': 'BCA605'},
        ],
        7: [  # Seventh Semester
            {'name': 'Cyber Law & Professional Ethics', 'code': 'BCA701'},
            {'name': 'Cloud Computing', 'code': 'BCA702'},
        ],
        8: [  # Eighth Semester
            {'name': 'Operation Research', 'code': 'BCA801'},
        ]
    }
    
    for semester, subjects in subjects_data.items():
        for subject_info in subjects:
            # Check if subject already exists
            existing = BCASubject.objects.filter(subject_code=subject_info['code']).first()
            if not existing:
                subject = BCASubject(
                    subject_name=subject_info['name'],
                    subject_code=subject_info['code'],
                    semester=semester
                )
                subject.save()
                print(f"Created: {subject}")
    
    print("BCA subjects populated successfully!")


def validate_semester(value):
    """Validate semester value"""
    if value not in range(1, 9):
        raise ValidationError('Semester must be between 1 and 8')


# Add this at the very end of courses/models.py
if __name__ == "__main__":
    populate_bca_subjects()