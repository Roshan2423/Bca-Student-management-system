# grades/models.py - Complete Grade Management System

from mongoengine import Document, StringField, DateTimeField, ReferenceField, IntField, BooleanField, FloatField, DateField
from datetime import datetime
from students.models import Student
from courses.models import Teacher, BCASubject

class ExamType(Document):
    """Different types of examinations"""
    
    EXAM_TYPES = [
        ('1st_terminal', '1st Terminal Exam'),
        ('mid_terminal', 'Mid Terminal Exam'),
        ('board_exam', 'Board Exam'),
    ]
    
    exam_code = StringField(max_length=20, required=True, unique=True, choices=EXAM_TYPES)
    exam_name = StringField(max_length=100, required=True)
    description = StringField()
    total_marks = IntField(default=60)  # Total marks for each exam
    pass_marks = IntField(default=24)   # Minimum marks to pass
    
    # Exam scheduling
    is_active = BooleanField(default=True)
    exam_date = DateField()
    created_at = DateTimeField(default=datetime.now)
    
    meta = {
        'collection': 'exam_types',
        'indexes': ['exam_code', 'is_active']
    }
    
    def __str__(self):
        return self.exam_name
    
    @property
    def pass_percentage(self):
        """Calculate pass percentage"""
        if self.total_marks > 0:
            return round((self.pass_marks / self.total_marks) * 100, 1)
        return 0


class StudentGrade(Document):
    """Individual grade record for a student in a specific subject and exam"""
    
    # Core references
    student = ReferenceField(Student, required=True)
    subject = ReferenceField(BCASubject, required=True)
    exam_type = ReferenceField(ExamType, required=True)
    
    # Grade details
    marks_obtained = IntField(required=True, min_value=0, max_value=60)
    total_marks = IntField(default=60)
    pass_marks = IntField(default=24)
    
    # Calculated fields
    is_pass = BooleanField(default=False)
    percentage = FloatField(default=0.0)
    grade_status = StringField(max_length=10, default='Fail')  # Pass/Fail
    
    # Administrative fields
    assigned_by = ReferenceField(Teacher, required=True)  # Teacher who assigned grade
    assigned_date = DateTimeField(default=datetime.now)
    remarks = StringField(max_length=500)  # Optional teacher remarks
    
    # Auto-populated fields for easier querying
    semester = IntField()  # Student's semester when grade was assigned
    academic_year = StringField(max_length=20, default='2024-25')
    
    meta = {
        'collection': 'student_grades',
        'indexes': [
            ('student', 'exam_type'),
            ('subject', 'exam_type'),
            ('semester', 'exam_type'),
            ('assigned_date'),
            'is_pass'
        ],
        # Ensure one grade per student per subject per exam type
        'unique_constraints': [('student', 'subject', 'exam_type')]
    }
    
    def save(self, *args, **kwargs):
        """Auto-calculate grade status before saving"""
        # Calculate percentage
        if self.total_marks > 0:
            self.percentage = round((self.marks_obtained / self.total_marks) * 100, 1)
        
        # Determine pass/fail status
        self.is_pass = self.marks_obtained >= self.pass_marks
        self.grade_status = 'Pass' if self.is_pass else 'Fail'
        
        # Set semester from student's current semester
        if self.student:
            self.semester = self.student.current_semester
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.student.full_name} - {self.subject.subject_name} - {self.exam_type.exam_name}: {self.marks_obtained}/{self.total_marks}"
    
    @classmethod
    def assign_grade(cls, student, subject, exam_type, marks_obtained, assigned_by, remarks=""):
        """Helper method to assign or update a grade"""
        # Check if grade already exists
        existing_grade = cls.objects.filter(
            student=student,
            subject=subject,
            exam_type=exam_type
        ).first()
        
        if existing_grade:
            # Update existing grade
            existing_grade.marks_obtained = marks_obtained
            existing_grade.assigned_by = assigned_by
            existing_grade.assigned_date = datetime.now()
            existing_grade.remarks = remarks
            existing_grade.save()
            return existing_grade
        else:
            # Create new grade
            grade = cls(
                student=student,
                subject=subject,
                exam_type=exam_type,
                marks_obtained=marks_obtained,
                assigned_by=assigned_by,
                remarks=remarks
            )
            grade.save()
            return grade
    
    @classmethod
    def get_student_grades(cls, student, exam_type=None):
        """Get all grades for a student, optionally filtered by exam type"""
        filters = {'student': student}
        if exam_type:
            filters['exam_type'] = exam_type
        
        return cls.objects.filter(**filters).order_by('subject__semester', 'subject__subject_name')
    
    @classmethod
    def get_semester_grades(cls, semester, exam_type):
        """Get all grades for a specific semester and exam type"""
        return cls.objects.filter(semester=semester, exam_type=exam_type)
    
    @property
    def grade_display(self):
        """Display grade with color coding info"""
        return {
            'marks': f"{self.marks_obtained}/{self.total_marks}",
            'percentage': f"{self.percentage}%",
            'status': self.grade_status,
            'color': 'success' if self.is_pass else 'danger'
        }


class GradeSummary(Document):
    """Summary of student's performance across all subjects for an exam type"""
    
    student = ReferenceField(Student, required=True)
    exam_type = ReferenceField(ExamType, required=True)
    semester = IntField(required=True)
    
    total_subjects = IntField(default=0)
    subjects_passed = IntField(default=0)
    subjects_failed = IntField(default=0)
    
    total_marks_obtained = IntField(default=0)
    total_marks_possible = IntField(default=0)
    overall_percentage = FloatField(default=0.0)
    
    overall_result = StringField(max_length=20, default='Fail')
    
    calculated_date = DateTimeField(default=datetime.now)
    academic_year = StringField(max_length=20, default='2024-25')
    
    meta = {
        'collection': 'grade_summaries',
        'indexes': [
            ('student', 'exam_type'),
            'semester',
            'overall_result'
        ],
        'unique_constraints': [('student', 'exam_type', 'semester')]
    }
    
    def __str__(self):
        return f"{self.student.full_name} - {self.exam_type.exam_name} - Semester {self.semester}: {self.overall_percentage}%"

    # ✅ FIXED: Now it's properly inside the class
    @classmethod
    def calculate_summary(cls, student, exam_type):
        """Calculate and save grade summary for a student and exam type"""
        grades = StudentGrade.objects.filter(student=student, exam_type=exam_type)

        if not grades:
            return None

        total_subjects = grades.count()
        subjects_passed = grades.filter(is_pass=True).count()
        subjects_failed = total_subjects - subjects_passed
        total_marks_obtained = sum(grade.marks_obtained for grade in grades)
        total_marks_possible = sum(grade.total_marks for grade in grades)

        overall_percentage = round((total_marks_obtained / total_marks_possible) * 100, 1) if total_marks_possible > 0 else 0
        overall_result = 'Pass' if subjects_failed == 0 else 'Fail'
        semester = student.current_semester

        summary = cls.objects.filter(
            student=student,
            exam_type=exam_type,
            semester=semester
        ).first()

        if not summary:
            summary = cls(
                student=student,
                exam_type=exam_type,
                semester=semester,
                total_subjects=total_subjects,
                subjects_passed=subjects_passed,
                subjects_failed=subjects_failed,
                total_marks_obtained=total_marks_obtained,
                total_marks_possible=total_marks_possible,
                overall_percentage=overall_percentage,
                overall_result=overall_result,
                calculated_date=datetime.now()
            )
        else:
            summary.total_subjects = total_subjects
            summary.subjects_passed = subjects_passed
            summary.subjects_failed = subjects_failed
            summary.total_marks_obtained = total_marks_obtained
            summary.total_marks_possible = total_marks_possible
            summary.overall_percentage = overall_percentage
            summary.overall_result = overall_result
            summary.calculated_date = datetime.now()

        summary.save()
        return summary





# Initialize default exam types
def create_default_exam_types():
    """Create default exam types if they don't exist"""
    exam_types_data = [
        {
            'exam_code': '1st_terminal',
            'exam_name': '1st Terminal Exam',
            'description': 'First terminal examination of the semester'
        },
        {
            'exam_code': 'mid_terminal',
            'exam_name': 'Mid Terminal Exam',
            'description': 'Mid terminal examination of the semester'
        },
        {
            'exam_code': 'board_exam',
            'exam_name': 'Board Exam',
            'description': 'Final board examination'
        }
    ]
    
    for exam_data in exam_types_data:
        existing = ExamType.objects.filter(exam_code=exam_data['exam_code']).first()
        if not existing:
            exam_type = ExamType(**exam_data)
            exam_type.save()
            print(f"Created exam type: {exam_type.exam_name}")

# Run this to create default exam types
if __name__ == "__main__":
    create_default_exam_types()