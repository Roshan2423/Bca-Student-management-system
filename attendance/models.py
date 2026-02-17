# attendance/models.py - FIXED VERSION with all imports

from mongoengine import Document, StringField, DateField, DateTimeField, ReferenceField, BooleanField, IntField
from datetime import datetime
from students.models import Student
from courses.models import Teacher

class DailyAttendance(Document):
    """Daily attendance record - one record per person per day"""
    
    # Person details (either student or teacher)
    student = ReferenceField(Student, required=False)
    teacher = ReferenceField(Teacher, required=False)
    
    # Attendance details
    date = DateField(required=True, default=datetime.now)
    is_present = BooleanField(required=True, default=False)
    
    # Teacher self-attendance workflow fields
    ATTENDANCE_STATUS = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('auto_approved', 'Auto Approved')  # For admin-marked attendance
    ]
    
    status = StringField(choices=ATTENDANCE_STATUS, default='pending')
    self_marked = BooleanField(default=False)  # True if teacher marked their own attendance
    
    # System fields
    marked_by = ReferenceField(Teacher, required=False)  # Who marked the attendance
    approved_by = ReferenceField(Teacher, required=False)  # Admin who approved/rejected
    marked_at = DateTimeField(default=datetime.now)
    approved_at = DateTimeField(required=False)
    notes = StringField(max_length=200, required=False)
    admin_notes = StringField(max_length=200, required=False)  # Admin feedback
    
    # Auto-generated fields
    person_type = StringField(choices=['student', 'teacher'], required=True)
    person_name = StringField(max_length=100, required=True)
    person_id = StringField(max_length=50, required=True)
    
    meta = {
        'collection': 'daily_attendance',
        'indexes': [
            ('date', 'person_type'),
            ('date', 'student'),
            ('date', 'teacher'),
            ('person_id', 'date'),
        ]
    }
    
    def save(self, *args, **kwargs):
        """Auto-populate fields before saving"""
        if self.student:
            self.person_type = 'student'
            self.person_name = f"{self.student.first_name} {self.student.last_name}"
            self.person_id = self.student.student_id
        elif self.teacher:
            self.person_type = 'teacher'
            self.person_name = f"{self.teacher.first_name} {self.teacher.last_name}"
            self.person_id = self.teacher.teacher_id
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        status = "Present" if self.is_present else "Absent"
        return f"{self.person_name} - {self.date} - {status}"
    
    @classmethod
    def mark_student_attendance(cls, student, date, is_present, marked_by=None, notes=""):
        """Mark attendance for a student on a specific date"""
        # Delete existing record for this date
        cls.objects.filter(student=student, date=date).delete()
        
        # Create new record
        attendance = cls(
            student=student,
            date=date,
            is_present=is_present,
            marked_by=marked_by,
            notes=notes
        )
        attendance.save()
        return attendance
    
    @classmethod
    def mark_teacher_attendance(cls, teacher, date, is_present, notes="", self_marked=False):
        """Mark attendance for a teacher on a specific date"""
        # Delete existing record for this date
        cls.objects.filter(teacher=teacher, date=date).delete()
        
        # Create new record
        attendance = cls(
            teacher=teacher,
            date=date,
            is_present=is_present,
            notes=notes,
            self_marked=self_marked,
            status='pending' if self_marked else 'auto_approved'
        )
        attendance.save()
        return attendance
    
    @classmethod
    def teacher_self_mark_attendance(cls, teacher, date, is_present, notes=""):
        """Teacher marks their own attendance - requires admin approval"""
        # Check if already marked for this date
        existing = cls.objects.filter(teacher=teacher, date=date).first()
        if existing:
            # Update existing record
            existing.is_present = is_present
            existing.notes = notes
            existing.self_marked = True
            existing.status = 'pending'
            existing.marked_at = datetime.now()
            existing.save()
            return existing
        
        # Create new self-marked record
        attendance = cls(
            teacher=teacher,
            date=date,
            is_present=is_present,
            notes=notes,
            self_marked=True,
            status='pending',
            marked_by=teacher
        )
        attendance.save()
        return attendance
    
    def approve_attendance(self, approver, admin_notes=""):
        """Admin approves teacher attendance"""
        self.status = 'approved'
        self.approved_by = approver
        self.approved_at = datetime.now()
        self.admin_notes = admin_notes
        self.save()
        return self
    
    def reject_attendance(self, approver, admin_notes=""):
        """Admin rejects teacher attendance"""
        self.status = 'rejected'
        self.approved_by = approver
        self.approved_at = datetime.now()
        self.admin_notes = admin_notes
        self.save()
        return self
    
    def get_status_display(self):
        """Get human-readable status"""
        status_map = {
            'pending': 'Pending Approval',
            'approved': 'Approved',
            'rejected': 'Rejected',
            'auto_approved': 'Auto Approved'
        }
        return status_map.get(self.status, self.status.title())
    
    @classmethod
    def get_student_attendance_stats(cls, student, days=30):
        """Get attendance statistics for a student"""
        from datetime import timedelta
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        records = cls.objects.filter(
            student=student,
            date__gte=start_date
        )
        
        total_days = records.count()
        present_days = records.filter(is_present=True).count()
        absent_days = total_days - present_days
        
        percentage = round((present_days / total_days * 100), 1) if total_days > 0 else 0
        
        return {
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'attendance_percentage': percentage
        }
    
    @classmethod
    def get_teacher_attendance_stats(cls, teacher, days=30):
        """Get attendance statistics for a teacher"""
        from datetime import timedelta
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        records = cls.objects.filter(
            teacher=teacher,
            date__gte=start_date,
            date__lte=end_date
        )
        
        total_days = records.count()
        present_days = records.filter(is_present=True).count()
        absent_days = total_days - present_days
        
        percentage = round((present_days / total_days * 100), 1) if total_days > 0 else 0
        
        return {
            'total_days': total_days,
            'present_days': present_days,
            'absent_days': absent_days,
            'attendance_percentage': percentage
        }