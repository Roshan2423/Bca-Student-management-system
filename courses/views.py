# Complete courses/views.py - BCA Course Management System with Teacher Management
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from mongoengine import DoesNotExist, Q
from .models import BCASubject, Teacher, CourseMaterial, Assignment, AssignmentSubmission, StudentEnrollment
from students.models import Student
from accounts.models import UserProfile
from django.http import FileResponse, Http404
from django.core.files.storage import default_storage
from django.views.decorators.http import require_http_methods
from .models import StudentFeeRecord, TeacherSalaryRecord
from django.urls import reverse
import json
import datetime
import mimetypes
import os
# Get the User model
User = get_user_model()
# ============================================================================
# STUDENT COURSE VIEWS
# ============================================================================
class StudentDashboardView(LoginRequiredMixin, TemplateView):
    """Student dashboard - shows only their semester subjects"""
    template_name = 'courses/student_dashboard.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            # Get current user's student profile
            student = Student.objects.filter(email=self.request.user.email).first()
            if not student:
                student = Student(
                    email=self.request.user.email,
                    first_name=self.request.user.first_name or "Student",
                    last_name=self.request.user.last_name or "",
                    student_id=f"STU{self.request.user.id:04d}",
                    current_semester=1
                )
                student.save()
            # Get enrollment info and ensure it's synced with student's current semester
            enrollment = StudentEnrollment.objects.filter(student=student).first()
            if not enrollment:
                enrollment = StudentEnrollment(
                    student=student,
                    current_semester=student.current_semester or 1
                )
                enrollment.save()
            else:
                # *** CRITICAL FIX: Sync enrollment with student's current semester ***
                if enrollment.current_semester != student.current_semester:
                    print(f"DEBUG: Semester mismatch detected! Student: {student.current_semester}, Enrollment: {enrollment.current_semester}")
                    enrollment.current_semester = student.current_semester
                    enrollment.save()
                    print(f"DEBUG: Updated enrollment semester to {student.current_semester}")
            
            # Get current semester subjects using student's current semester (the source of truth)
            semester_subjects_raw = BCASubject.objects.filter(semester=student.current_semester)
            semester_subjects = []
            for subject in semester_subjects_raw:
                safe_subject = {
                    'id': subject.id,
                    'subject_code': subject.subject_code,
                    'subject_name': subject.subject_name,
                    'description': getattr(subject, 'description', ''),
                    'credit_hours': getattr(subject, 'credit_hours', 3),
                    'semester': subject.semester,
                    'assigned_teacher': None,
                    'teacher_name': 'No teacher assigned'
                }
                try:
                    if hasattr(subject, 'assigned_teacher') and subject.assigned_teacher:
                        teacher = subject.assigned_teacher
                        safe_subject['assigned_teacher'] = teacher
                        safe_subject['teacher_name'] = f"{teacher.first_name} {teacher.last_name}"
                except Exception as e:
                    print(f"DEBUG: Broken teacher reference for {subject.subject_code}: {e}")
                    try:
                        subject.assigned_teacher = None
                        subject.save()
                    except:
                        pass
                semester_subjects.append(safe_subject)
            # --- Fee Payment Status Logic (improved) ---
            current_semester = student.current_semester  # Use student's semester as source of truth
            # Create missing fee records automatically
            for sem in range(1, current_semester + 1):
                existing = StudentFeeRecord.objects.filter(student=student, semester=sem).first()
                if not existing:
                    new_fee = StudentFeeRecord(
                        student=student,
                        semester=sem,
                        total_fee=50000.0,
                        paid_amount=0.0
                    )
                    new_fee.save()
                    print(f"DEBUG: Created missing fee record for Semester {sem}")
            # Re-fetch fee records after creating missing ones
            fee_records = StudentFeeRecord.objects.filter(student=student, semester__lte=current_semester)
            total_paid = sum(fee.paid_amount for fee in fee_records)
            expected_fee = current_semester * 50000  # Rs.50,000 per semester
            # *** NEW LOGIC: Check every semester is fully paid ***
            all_semesters_paid = True
            for sem in range(1, current_semester + 1):
                fee_record = StudentFeeRecord.objects.filter(student=student, semester=sem).first()
                if not fee_record or fee_record.paid_amount < fee_record.total_fee:
                    all_semesters_paid = False
                    break
            # Determine enrollment status with strict logic
            if all_semesters_paid:
                enrollment_status = "Full Paid"
            elif total_paid >= (expected_fee * 0.5):
                enrollment_status = "Half Paid"
            elif total_paid > 0:
                enrollment_status = "Partially Paid"
            else:
                enrollment_status = "Not Paid"
            enrollment.payment_status = enrollment_status
            # Additional detailed fee breakdown for debugging
            fee_breakdown = []
            for sem in range(1, current_semester + 1):
                fee_record = StudentFeeRecord.objects.filter(student=student, semester=sem).first()
                if fee_record:
                    fee_breakdown.append({
                        'semester': sem,
                        'expected': fee_record.total_fee,
                        'paid': fee_record.paid_amount,
                        'status': fee_record.payment_status,
                        'completion': round((fee_record.paid_amount / fee_record.total_fee * 100), 1) if fee_record.total_fee > 0 else 0
                    })
            # Enhanced debug info
            print(f"[DEBUG] ==========================================")
            print(f"[DEBUG] Student: {student.full_name}")
            print(f"[DEBUG] Email: {student.email}")
            print(f"[DEBUG] Current Semester: {current_semester}")
            print(f"[DEBUG] Expected Total Fee: Rs.{expected_fee:,}")
            print(f"[DEBUG] Total Paid: Rs.{total_paid:,}")
            print(f"[DEBUG] Enrollment Status: {enrollment_status}")
            print(f"[DEBUG] Fee Records Count: {len(fee_records)}")
            print(f"[DEBUG] enrollment.payment_status: {enrollment.payment_status}")
            print(f"[DEBUG] Fee Records Detail:")
            for fee in fee_breakdown:
                print(f"[DEBUG]   Semester {fee['semester']}: Rs.{fee['paid']:,}/{fee['expected']:,} ({fee['completion']}%) - {fee['status']}")
            print(f"[DEBUG] ==========================================")
            
            # Calculate only the count of pending assignments for stats (detailed view will be in StudentAssignmentsView)
            total_pending_count = 0
            
            for subject_dict in semester_subjects:
                try:
                    subject = BCASubject.objects.get(subject_code=subject_dict['subject_code'])
                    # Get assignments for this subject - ONLY THOSE CREATED AFTER STUDENT ENROLLMENT
                    subject_assignments = Assignment.objects.filter(
                        subject=subject,
                        created_date__gte=student.created_at  # Only assignments created after student joined
                    ).order_by('-created_date')
                    print(f"DASHBOARD FILTER: Student {student.full_name} sees {subject_assignments.count()} assignments for {subject.subject_code} (created after {student.created_at})")
                    
                    for assignment in subject_assignments:
                        # Check if student has submitted this assignment
                        submission = AssignmentSubmission.objects.filter(
                            assignment=assignment,
                            student=student
                        ).first()
                        
                        # If not submitted and not overdue, it's pending
                        if not submission and not assignment.is_overdue:
                            total_pending_count += 1
                            
                except Exception as e:
                    print(f"DEBUG: Error processing assignments for {subject_dict['subject_code']}: {e}")
                    continue
            
            print(f"DEBUG: Total pending assignments found: {total_pending_count}")
            
            context.update({
                'student': student,
                'enrollment': enrollment,  # Now has payment_status attribute
                'semester_subjects': semester_subjects,
                'current_semester': current_semester,
                'enrollment_status': enrollment_status,  # Keep this too for compatibility
                'total_paid': total_paid,
                'expected_fee': expected_fee,
                'fee_breakdown': fee_breakdown,  # For template debugging
                'pending_assignments_count': total_pending_count,  # Add count for stats
                'debug_info': {
                    'user_email': self.request.user.email,
                    'student_found': True,
                    'subjects_count': len(semester_subjects),
                    'total_paid': total_paid,
                    'expected_fee': expected_fee,
                    'fee_records_count': len(fee_records),
                    'enrollment_payment_status': enrollment.payment_status,
                    'fee_breakdown': fee_breakdown  # Add to debug info
                }
            })
        except Exception as e:
            print(f"DEBUG: Error in StudentDashboardView: {e}")
            import traceback
            traceback.print_exc()
            messages.error(self.request, f'Error loading dashboard: {str(e)}')
            context.update({
                'student': None,
                'enrollment': None,
                'semester_subjects': [],
                'current_semester': 1,
                'enrollment_status': "Not Paid",
                'debug_info': {
                    'user_email': self.request.user.email,
                    'student_found': False,
                    'error': str(e)
                }
            })
        return context
class SubjectDetailView(LoginRequiredMixin, TemplateView):
    """View specific subject details, materials, and assignments - FIXED VERSION"""
    template_name = 'courses/subject_detail.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject_code = kwargs.get('subject_code')
        try:
            # Get the specific subject by subject_code
            subject = BCASubject.objects.get(subject_code=subject_code)
            print(f"DEBUG: Found subject: {subject.subject_name} ({subject.subject_code})")
            # ENHANCED Security check: Student can only access their semester subjects
            if self.request.user.role == 'student':
                student = Student.objects.get(email=self.request.user.email)
                enrollment = StudentEnrollment.objects.filter(student=student).first()
                
                # Ensure enrollment is synced with student's current semester
                if enrollment and enrollment.current_semester != student.current_semester:
                    print(f"SECURITY: Syncing enrollment for {student.full_name}: {enrollment.current_semester} → {student.current_semester}")
                    enrollment.current_semester = student.current_semester
                    enrollment.save()
                
                # CRITICAL: Strict semester access control
                if not enrollment or subject.semester != student.current_semester:
                    print(f"SECURITY VIOLATION: Student {student.full_name} (semester {student.current_semester}) attempted to access {subject.subject_code} (semester {subject.semester})")
                    messages.error(self.request, f'Access denied! You can only access Semester {student.current_semester} subjects. This is Semester {subject.semester}.')
                    context['subject'] = None
                    return context
                    
                # Additional validation: Double-check subject belongs to student's semester
                valid_subjects = BCASubject.objects.filter(semester=student.current_semester)
                if subject not in valid_subjects:
                    print(f"SECURITY VIOLATION: Subject {subject.subject_code} not in valid subjects for semester {student.current_semester}")
                    messages.error(self.request, 'This subject is not available for your current semester!')
                    context['subject'] = None
                    return context
            # Get course materials - FILTER BY THIS SPECIFIC SUBJECT ONLY
            materials = CourseMaterial.objects.filter(
                subject=subject,  # <- This is the key fix
                is_active=True
            ).order_by('-upload_date')
            print(f"DEBUG: Found {materials.count()} materials for {subject.subject_code}")
            for material in materials:
                print(f"  - {material.title} (Subject: {material.subject.subject_code})")
            # Get assignments - FILTER BY SUBJECT AND STUDENT ENROLLMENT DATE
            assignments_query = Assignment.objects.filter(subject=subject)
            
            # CRITICAL FIX: For students, only show assignments created after their enrollment
            if self.request.user.role == 'student':
                student = Student.objects.get(email=self.request.user.email)
                # Only show assignments created after student's enrollment/creation date
                assignments = assignments_query.filter(
                    created_date__gte=student.created_at
                ).order_by('-created_date')
                print(f"FILTERED: Student {student.full_name} enrolled {student.created_at}, showing {assignments.count()} assignments created after enrollment")
            else:
                # Teachers/admins see all assignments
                assignments = assignments_query.order_by('-created_date')
            print(f"DEBUG: Found {assignments.count()} assignments for {subject.subject_code}")
            for assignment in assignments:
                print(f"  - {assignment.title} (Subject: {assignment.subject.subject_code})")
            # Get student's submissions (if student)
            submissions = []
            submission_dict = {}
            if self.request.user.role == 'student':
                try:
                    student = Student.objects.get(email=self.request.user.email)
                    submissions = AssignmentSubmission.objects.filter(
                        assignment__in=assignments,  # Only assignments for this subject
                        student=student
                    )
                    
                    # Sort submissions: latest submission date first (most recent at top)
                    submissions = sorted(submissions, key=lambda x: x.submission_date, reverse=True)
                    
                    # Create lookup dictionary for template
                    for submission in submissions:
                        submission_dict[str(submission.assignment.id)] = submission
                except Student.DoesNotExist:
                    print("DEBUG: Student profile not found")
                    pass
            # Get teacher information safely
            teacher_info = None
            teacher_name = "No teacher assigned"
            try:
                if hasattr(subject, 'assigned_teacher') and subject.assigned_teacher:
                    teacher = subject.assigned_teacher
                    teacher_info = teacher
                    teacher_name = f"{teacher.first_name} {teacher.last_name}"
            except Exception as e:
                print(f"DEBUG: Teacher reference error: {e}")
                teacher_name = "Teacher assignment error"
            # Calculate pending assignments for student (not submitted yet and not overdue)
            pending_assignments_count = 0
            if self.request.user.role == 'student':
                try:
                    student = Student.objects.get(email=self.request.user.email)
                    for assignment in assignments:
                        # Check if student has submitted this assignment
                        submission = AssignmentSubmission.objects.filter(
                            assignment=assignment,
                            student=student
                        ).first()
                        
                        if not submission and not assignment.is_overdue:
                            # Not submitted and not overdue = pending
                            pending_assignments_count += 1
                            print(f"DEBUG: Student pending assignment: {assignment.title}")
                        elif submission:
                            print(f"DEBUG: Student already submitted: {assignment.title} (Status: {submission.status})")
                        elif assignment.is_overdue:
                            print(f"DEBUG: Student missed deadline: {assignment.title}")
                            
                    print(f"DEBUG: Total pending assignments for student: {pending_assignments_count}")
                except Student.DoesNotExist:
                    print("DEBUG: Student not found")
            else:
                # For teachers/admins, show active assignments (not yet due)
                pending_assignments = assignments.filter(
                    due_date__gt=datetime.datetime.now()
                ) if assignments else []
                pending_assignments_count = len(pending_assignments)
            # Calculate pending submissions (submitted work waiting for grading)
            pending_submissions_count = 0
            if self.request.user.role in ['teacher', 'admin']:
                try:
                    for assignment in assignments:
                        submitted_work = AssignmentSubmission.objects.filter(
                            assignment=assignment,
                            status='submitted'
                        )
                        pending_submissions_count += submitted_work.count()
                except Exception as e:
                    print(f"DEBUG: Error calculating pending submissions: {e}")
            context.update({
                'subject': subject,
                'materials': materials,
                'assignments': assignments,
                'submissions': submissions,
                'submission_dict': submission_dict,  # For easy template lookup
                'teacher_info': teacher_info,
                'teacher_name': teacher_name,
                'is_teacher': self.request.user.role in ['teacher', 'admin'],
                'is_student': self.request.user.role == 'student',
                'pending_assignments': pending_assignments_count,  # Updated to use count
                'pending_submissions': pending_submissions_count,
                # Debug info
                'debug_info': {
                    'subject_code': subject_code,
                    'subject_name': subject.subject_name,
                    'materials_count': materials.count(),
                    'assignments_count': assignments.count(),
                    'submissions_count': len(submissions),
                    'pending_assignments_count': pending_assignments_count,  # Updated to use count
                    'pending_submissions_count': pending_submissions_count
                }
            })
        except BCASubject.DoesNotExist:
            print(f"DEBUG: Subject {subject_code} not found")
            messages.error(self.request, f'Subject {subject_code} not found!')
            context.update({
                'subject': None,
                'materials': [],
                'assignments': [],
                'submissions': [],
                'debug_info': {'error': f'Subject {subject_code} not found'}
            })
        except Student.DoesNotExist:
            if self.request.user.role == 'student':
                print("DEBUG: Student profile not found")
                messages.error(self.request, 'Student profile not found!')
                context['subject'] = None
        except Exception as e:
            print(f"DEBUG: Unexpected error in SubjectDetailView: {e}")
            messages.error(self.request, f'Error loading subject details: {str(e)}')
            context.update({
                'subject': None,
                'materials': [],
                'assignments': [],
                'submissions': [],
                'debug_info': {'error': str(e)}
            })
        return context
class SubmitAssignmentView(LoginRequiredMixin, TemplateView):
    """Submit assignment (student)"""
    template_name = 'courses/submit_assignment.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment_id = kwargs.get('assignment_id')
        if self.request.user.role != 'student':
            messages.error(self.request, 'Only students can submit assignments!')
            return context
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            student = Student.objects.get(email=self.request.user.email)
            
            # CRITICAL SECURITY CHECK: Ensure student can only submit to assignments in their semester
            if assignment.subject.semester != student.current_semester:
                print(f"SECURITY VIOLATION: Student {student.full_name} (semester {student.current_semester}) attempted to submit to assignment in semester {assignment.subject.semester}")
                messages.error(self.request, f'Access denied! You can only submit assignments for Semester {student.current_semester}. This assignment is for Semester {assignment.subject.semester}.')
                return redirect('courses:student-dashboard')
            # Check if already submitted (allow resubmission if rejected)
            existing_submission = AssignmentSubmission.objects.filter(
                assignment=assignment,
                student=student
            ).first()
            
            # Allow resubmission if previous submission was rejected
            can_resubmit = existing_submission is None or existing_submission.status == 'rejected'
            
            context.update({
                'assignment': assignment,
                'existing_submission': existing_submission,
                'is_overdue': assignment.is_overdue,
                'can_resubmit': can_resubmit,
                'is_rejected': existing_submission and existing_submission.status == 'rejected'
            })
        except (Assignment.DoesNotExist, Student.DoesNotExist):
            messages.error(self.request, 'Assignment or student not found!')
            context['assignment'] = None
        return context
    def post(self, request, *args, **kwargs):
        assignment_id = kwargs.get('assignment_id')
        if request.user.role != 'student':
            messages.error(request, 'Access denied!')
            return redirect('courses:student-dashboard')
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            student = Student.objects.get(email=request.user.email)
            
            # CRITICAL SECURITY CHECK: Ensure student can only submit to assignments in their semester
            if assignment.subject.semester != student.current_semester:
                print(f"SECURITY VIOLATION: Student {student.full_name} (semester {student.current_semester}) attempted to submit to assignment in semester {assignment.subject.semester}")
                messages.error(request, f'Access denied! You can only submit assignments for Semester {student.current_semester}. This assignment is for Semester {assignment.subject.semester}.')
                return redirect('courses:student-dashboard')
            # Check if already submitted (allow resubmission if rejected)
            existing_submission = AssignmentSubmission.objects.filter(
                assignment=assignment,
                student=student
            ).first()
            
            if existing_submission and existing_submission.status != 'rejected':
                messages.warning(request, 'You have already submitted this assignment!')
                return redirect('courses:subject-detail', subject_code=assignment.subject.subject_code)
            elif existing_submission and existing_submission.status == 'rejected':
                # Delete the rejected submission to allow new submission
                existing_submission.delete()
                messages.info(request, 'Previous submission was rejected. You can now submit a new version.')
            # Create submission
            submission = AssignmentSubmission(
                assignment=assignment,
                student=student,
                submission_text=request.POST.get('submission_text', '')
            )
            # Handle file upload
            submission_file = request.FILES.get('submission_file')
            if submission_file:
                file_path = f"submissions/{assignment_id}/{student.student_id}_{submission_file.name}"
                saved_path = default_storage.save(file_path, submission_file)
                submission.submission_file_path = saved_path
                submission.submission_file_name = submission_file.name
                submission.file_size = submission_file.size
            # Check if late
            submission.calculate_status()
            submission.save()
            if submission.is_late:
                messages.warning(request, 'Assignment submitted late!')
            else:
                messages.success(request, 'Assignment submitted successfully!')
            return redirect('courses:subject-detail', subject_code=assignment.subject.subject_code)
        except Exception as e:
            messages.error(request, f'Error submitting assignment: {str(e)}')
            return self.get(request, *args, **kwargs)
# ============================================================================
# TEACHER COURSE VIEWS
# ============================================================================
class TeacherDashboardView(LoginRequiredMixin, TemplateView):
    """Teacher dashboard - shows subjects they teach"""
    template_name = 'courses/teacher_dashboard.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role not in ['teacher', 'admin']:
            messages.error(self.request, 'Access denied!')
            return context
        try:
            # Debug: Print user email
            user_email = self.request.user.email
            print(f"DEBUG: Looking for teacher with email: '{user_email}'")
            # Get teacher profile with exact email match
            teacher = Teacher.objects.filter(email=user_email).first()
            print(f"DEBUG: Found teacher: {teacher}")
            if not teacher:
                # Debug: Show all teacher emails
                all_teachers = Teacher.objects.all()
                print(f"DEBUG: All teacher emails in database:")
                for t in all_teachers:
                    print(f"  - '{t.email}' (Teacher: {t.first_name} {t.last_name})")
                messages.warning(self.request, 'Teacher profile not found. Please contact admin.')
                context.update({
                    'teacher': None,
                    'assigned_subjects': [],
                    'recent_assignments': [],
                    'pending_submissions': 0,
                    'debug_email': user_email
                })
                return context
            print(f"DEBUG: Teacher found - {teacher.first_name} {teacher.last_name}")
            # Get subjects assigned to this teacher
            assigned_subjects = BCASubject.objects.filter(assigned_teacher=teacher)
            print(f"DEBUG: Found {assigned_subjects.count()} assigned subjects")
            # Get recent assignments and calculate counts per subject (avoid MongoDB join issues)
            recent_assignments = []
            pending_submissions = 0
            
            # Add calculated counts to each subject
            subjects_with_counts = []
            for subject in assigned_subjects:
                try:
                    # Get assignments for this specific subject
                    subject_assignments = Assignment.objects.filter(subject=subject).order_by('-created_date')
                    print(f"DEBUG: Found {subject_assignments.count()} assignments for {subject.subject_code}")
                    
                    # Count active assignments (not yet due)
                    current_time = datetime.datetime.now()
                    active_assignments = []
                    for assignment in subject_assignments:
                        if assignment.due_date > current_time:
                            active_assignments.append(assignment)
                    
                    # Count pending submissions for this subject (only truly pending ones)
                    subject_pending = 0
                    for assignment in subject_assignments:
                        pending_subs = AssignmentSubmission.objects.filter(
                            assignment=assignment,
                            status='submitted'  # Only submitted (not approved, rejected, or graded)
                        )
                        subject_pending += pending_subs.count()
                        
                        # Debug: Log what we're counting
                        all_subs = AssignmentSubmission.objects.filter(assignment=assignment)
                        print(f"DEBUG: Assignment '{assignment.title}' - Total submissions: {all_subs.count()}")
                        for sub in all_subs:
                            print(f"  - Student {sub.student.full_name}: Status = '{sub.status}'")
                        print(f"  - Truly pending (status='submitted'): {pending_subs.count()}")
                    
                    # Add to total pending count
                    pending_submissions += subject_pending
                    
                    # Add recent assignments from this subject to global list
                    for assignment in subject_assignments[:2]:  # Get 2 most recent per subject
                        recent_assignments.append(assignment)
                    
                    # Create subject with counts for template
                    subject_dict = {
                        'subject': subject,
                        'active_count': len(active_assignments),
                        'pending_count': subject_pending,
                        'total_assignments': subject_assignments.count()
                    }
                    subjects_with_counts.append(subject_dict)
                    
                    print(f"DEBUG: Subject {subject.subject_code} - Active: {len(active_assignments)}, Pending: {subject_pending}")
                    
                except Exception as e:
                    print(f"DEBUG: Error processing subject {subject.subject_code}: {e}")
                    # Add subject with zero counts if there's an error
                    subjects_with_counts.append({
                        'subject': subject,
                        'active_count': 0,
                        'pending_count': 0,
                        'total_assignments': 0
                    })
            
            # Sort recent assignments by date and limit to 5
            recent_assignments.sort(key=lambda x: x.created_date if hasattr(x, 'created_date') else datetime.datetime.now(), reverse=True)
            recent_assignments = recent_assignments[:5]
            
            print(f"DEBUG: Total pending submissions across all subjects: {pending_submissions}")
            context.update({
                'teacher': teacher,
                'assigned_subjects': assigned_subjects,
                'subjects_with_counts': subjects_with_counts,  # Add subjects with individual counts
                'recent_assignments': recent_assignments,
                'pending_submissions': pending_submissions,
                'debug_email': user_email
            })
        except Exception as e:
            print(f"DEBUG: Major error in teacher dashboard: {e}")
            messages.error(self.request, f'Error loading teacher dashboard: {str(e)}')
            context.update({
                'teacher': None,
                'assigned_subjects': [],
                'recent_assignments': [],
                'pending_submissions': 0,
                'debug_email': self.request.user.email,
                'error': str(e)
            })
        return context
class SubjectStudentsView(LoginRequiredMixin, TemplateView):
    """View students enrolled in a specific subject"""
    template_name = 'courses/subject_students.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject_code = kwargs.get('subject_code')
        # Check if user is teacher or admin
        if self.request.user.role not in ['teacher', 'admin']:
            messages.error(self.request, 'Access denied! Only teachers and admins can view student lists.')
            return context
        try:
            # Get the subject
            subject = BCASubject.objects.get(subject_code=subject_code)
            # Check if teacher is assigned to this subject (unless admin)
            if self.request.user.role == 'teacher':
                teacher = Teacher.objects.filter(email=self.request.user.email).first()
                if not teacher or subject.assigned_teacher != teacher:
                    messages.error(self.request, 'You can only view students for subjects assigned to you.')
                    return context
            # Get all students enrolled in this subject's semester
            students_in_semester = Student.objects.filter(
                current_semester=subject.semester,
                is_active=True
            ).order_by('first_name', 'last_name')
            # Enhanced student data with additional info
            student_data = []
            for student in students_in_semester:
                # Get enrollment info
                enrollment = StudentEnrollment.objects.filter(student=student).first()
                # Get fee status for current semester
                fee_record = StudentFeeRecord.objects.filter(
                    student=student,
                    semester=subject.semester
                ).first()
                # Determine fee status
                fee_status = "Not Paid"
                fee_completion = 0
                if fee_record:
                    if fee_record.is_completed:
                        fee_status = "Fully Paid"
                        fee_completion = 100
                    elif fee_record.paid_amount > 0:
                        fee_status = "Partially Paid"
                        fee_completion = round((fee_record.paid_amount / fee_record.total_fee) * 100, 1)
                # Check if student has submitted assignments for this subject
                assignments_for_subject = Assignment.objects.filter(subject=subject)
                total_assignments = assignments_for_subject.count()
                submitted_assignments = 0
                for assignment in assignments_for_subject:
                    submission = AssignmentSubmission.objects.filter(
                        assignment=assignment,
                        student=student
                    ).first()
                    if submission:
                        submitted_assignments += 1
                assignment_completion = round((submitted_assignments / total_assignments) * 100, 1) if total_assignments > 0 else 0
                student_data.append({
                    'student': student,
                    'enrollment': enrollment,
                    'fee_status': fee_status,
                    'fee_completion': fee_completion,
                    'total_assignments': total_assignments,
                    'submitted_assignments': submitted_assignments,
                    'assignment_completion': assignment_completion,
                })
            # Get subject statistics
            total_students = len(student_data)
            fully_paid_students = len([s for s in student_data if s['fee_status'] == 'Fully Paid'])
            active_students = len([s for s in student_data if s['student'].is_active])
            # Search functionality
            search_query = self.request.GET.get('search', '').strip()
            if search_query:
                filtered_data = []
                for data in student_data:
                    student = data['student']
                    if (search_query.lower() in student.first_name.lower() or
                        search_query.lower() in student.last_name.lower() or
                        search_query.lower() in student.email.lower() or
                        search_query.lower() in student.student_id.lower() or
                        (student.phone_number and search_query in student.phone_number)):
                        filtered_data.append(data)
                student_data = filtered_data
            context.update({
                'subject': subject,
                'student_data': student_data,
                'total_students': total_students,
                'fully_paid_students': fully_paid_students,
                'active_students': active_students,
                'search_query': search_query,
                'can_manage_students': self.request.user.role == 'admin'
            })
        except BCASubject.DoesNotExist:
            messages.error(self.request, f'Subject {subject_code} not found!')
            context['subject'] = None
        except Exception as e:
            messages.error(self.request, f'Error loading students: {str(e)}')
            context['subject'] = None
        return context
class UploadMaterialView(LoginRequiredMixin, TemplateView):
    """Upload course materials (PDFs, etc.)"""
    template_name = 'courses/upload_material.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject_code = kwargs.get('subject_code')
        if self.request.user.role not in ['teacher', 'admin']:
            messages.error(self.request, 'Access denied!')
            return context
        try:
            subject = BCASubject.objects.get(subject_code=subject_code)
            context['subject'] = subject
        except BCASubject.DoesNotExist:
            messages.error(self.request, 'Subject not found!')
            context['subject'] = None
        return context
    def post(self, request, *args, **kwargs):
        subject_code = kwargs.get('subject_code')
        if request.user.role not in ['teacher', 'admin']:
            messages.error(request, 'Access denied!')
            return redirect('courses:teacher-dashboard')
        try:
            subject = BCASubject.objects.get(subject_code=subject_code)
            teacher = Teacher.objects.get(email=request.user.email)
            # Handle file upload
            uploaded_file = request.FILES.get('material_file')
            if not uploaded_file:
                messages.error(request, 'Please select a file to upload!')
                return self.get(request, *args, **kwargs)
            # Save file
            file_name = uploaded_file.name
            file_path = f"course_materials/{subject_code}/{file_name}"
            saved_path = default_storage.save(file_path, uploaded_file)
            # Create material record
            material = CourseMaterial(
                subject=subject,
                title=request.POST.get('title'),
                description=request.POST.get('description', ''),
                material_type=request.POST.get('material_type', 'pdf'),
                file_path=saved_path,
                file_name=file_name,
                file_size=uploaded_file.size,
                uploaded_by=teacher
            )
            material.save()
            messages.success(request, f'Material "{material.title}" uploaded successfully!')
            return redirect('courses:subject-detail', subject_code=subject_code)
        except Exception as e:
            messages.error(request, f'Error uploading material: {str(e)}')
            return self.get(request, *args, **kwargs)
class CreateAssignmentView(LoginRequiredMixin, TemplateView):
    """Create new assignment"""
    template_name = 'courses/create_assignment.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject_code = kwargs.get('subject_code')
        if self.request.user.role not in ['teacher', 'admin']:
            messages.error(self.request, 'Access denied!')
            return context
        try:
            subject = BCASubject.objects.get(subject_code=subject_code)
            context['subject'] = subject
        except BCASubject.DoesNotExist:
            messages.error(self.request, 'Subject not found!')
            context['subject'] = None
        return context
    def post(self, request, *args, **kwargs):
        subject_code = kwargs.get('subject_code')
        if request.user.role not in ['teacher', 'admin']:
            messages.error(request, 'Access denied!')
            return redirect('courses:teacher-dashboard')
        try:
            subject = BCASubject.objects.get(subject_code=subject_code)
            teacher = Teacher.objects.get(email=request.user.email)
            # Parse due date
            due_date_str = request.POST.get('due_date')
            due_time_str = request.POST.get('due_time', '23:59')
            due_datetime = datetime.datetime.strptime(
                f"{due_date_str} {due_time_str}", 
                '%Y-%m-%d %H:%M'
            )
            # Create assignment
            assignment = Assignment(
                subject=subject,
                title=request.POST.get('title'),
                description=request.POST.get('description'),
                instructions=request.POST.get('instructions', ''),
                created_by=teacher,
                due_date=due_datetime,
            )
            # Handle optional assignment file
            assignment_file = request.FILES.get('assignment_file')
            if assignment_file:
                file_path = f"assignments/{subject_code}/{assignment_file.name}"
                saved_path = default_storage.save(file_path, assignment_file)
                assignment.assignment_file_path = saved_path
                assignment.assignment_file_name = assignment_file.name
            assignment.save()
            messages.success(request, f'Assignment "{assignment.title}" created successfully!')
            return redirect('courses:subject-detail', subject_code=subject_code)
        except Exception as e:
            messages.error(request, f'Error creating assignment: {str(e)}')
            return self.get(request, *args, **kwargs)
# ============================================================================
# TEACHER MANAGEMENT VIEWS
# ============================================================================
class TeacherCreateView(LoginRequiredMixin, TemplateView):
    """Create new teacher with complete profile information"""
    template_name = 'courses/teacher_create.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role not in ['admin']:
            messages.error(self.request, 'Access denied! Only admin can create teachers.')
            return context
        # Get all BCA subjects for assignment
        all_subjects = BCASubject.objects.all().order_by('semester', 'subject_name')
        context.update({
            'all_subjects': all_subjects,
            'departments': [
                'Computer Science', 
                'Information Technology', 
                'Management', 
                'Mathematics', 
                'English'
            ],
            'designations': [
                'Professor', 
                'Associate Professor',
                'Assistant Professor', 
                'Lecturer', 
                'Senior Lecturer', 
                'Department Head'
            ],
            'employment_types': [
                ('full_time', 'Full Time'),
                ('contract', 'Contract')
            ]
        })
        return context
    def post(self, request, *args, **kwargs):
        if request.user.role not in ['admin']:
            messages.error(request, 'Access denied!')
            return redirect('courses:teacher-list')
        try:
            # Get form data
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            email = request.POST.get('email', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            address = request.POST.get('address', '').strip()
            date_of_birth_str = request.POST.get('date_of_birth', '')
            gender = request.POST.get('gender', '')
            teacher_id = request.POST.get('teacher_id', '').strip()
            department = request.POST.get('department', '').strip()
            designation = request.POST.get('designation', '').strip()
            qualification = request.POST.get('qualification', '').strip()
            experience_years = request.POST.get('experience_years', '0')
            joining_date_str = request.POST.get('joining_date', '')
            employment_type = request.POST.get('employment_type', 'full_time')
            salary_str = request.POST.get('salary', '')
            emergency_contact_name = request.POST.get('emergency_contact_name', '').strip()
            emergency_contact_phone = request.POST.get('emergency_contact_phone', '').strip()
            emergency_contact_relation = request.POST.get('emergency_contact_relation', '').strip()
            subjects_teaching = request.POST.getlist('subjects_teaching')
            notes = request.POST.get('notes', '').strip()
            create_account = request.POST.get('create_account') == 'on'
            # Validate required fields
            required_fields = {
                'first_name': first_name,
                'last_name': last_name,
                'email': email,
                'teacher_id': teacher_id,
                'department': department,
                'designation': designation
            }
            missing_fields = [name for name, value in required_fields.items() if not value]
            if missing_fields:
                messages.error(request, f'Please fill in required fields: {", ".join(missing_fields)}')
                return self.get(request, *args, **kwargs)
            # Check if teacher ID or email already exists
            if Teacher.objects.filter(teacher_id=teacher_id).first():
                messages.error(request, f'Teacher ID {teacher_id} already exists!')
                return self.get(request, *args, **kwargs)
            if Teacher.objects.filter(email=email).first():
                messages.error(request, f'Email {email} already exists!')
                return self.get(request, *args, **kwargs)
            # Parse dates
            date_of_birth = None
            if date_of_birth_str:
                try:
                    date_of_birth = datetime.datetime.strptime(date_of_birth_str, '%Y-%m-%d')
                except ValueError:
                    pass
            joining_date = datetime.datetime.now()
            if joining_date_str:
                try:
                    joining_date = datetime.datetime.strptime(joining_date_str, '%Y-%m-%d')
                except ValueError:
                    pass
            # Parse numeric fields
            try:
                experience_years = int(experience_years) if experience_years else 0
            except ValueError:
                experience_years = 0
            salary = None
            if salary_str:
                try:
                    salary = float(salary_str)
                except ValueError:
                    pass
            # Create teacher
            teacher = Teacher(
                # Personal Information
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone_number=phone_number,
                address=address,
                date_of_birth=date_of_birth,
                gender=gender,
                # Teacher Information
                teacher_id=teacher_id,
                department=department,
                designation=designation,
                qualification=qualification,
                experience_years=experience_years,
                # Employment Information
                joining_date=joining_date,
                employment_type=employment_type,
                salary=salary,
                # Emergency Contact
                emergency_contact_name=emergency_contact_name,
                emergency_contact_phone=emergency_contact_phone,
                emergency_contact_relation=emergency_contact_relation,
                # System Fields
                subjects_teaching=subjects_teaching,
                notes=notes
            )
            teacher.save()
            # Create user account if requested
            generated_password = None
            if create_account:
                try:
                    django_user, generated_password = teacher.create_user_account()
                    messages.success(
                        request,
                        f'Teacher account created successfully! '
                        f'Login Email: {email}, Password: {generated_password} '
                        f'(Please share this password securely with the teacher)'
                    )
                except Exception as e:
                    messages.warning(
                        request,
                        f'Teacher profile created but user account creation failed: {str(e)}. '
                        f'You can create the account later.'
                    )
            # Assign teacher to selected BCA subjects
            assigned_count = 0
            for subject_code in subjects_teaching:
                try:
                    subject = BCASubject.objects.get(subject_code=subject_code)
                    subject.assigned_teacher = teacher
                    subject.save()
                    assigned_count += 1
                except BCASubject.DoesNotExist:
                    continue
            success_message = f'Teacher {teacher.full_name} created successfully!'
            if assigned_count > 0:
                success_message += f' Assigned to {assigned_count} subjects.'
            messages.success(request, success_message)
            return redirect('courses:teacher-list')
        except Exception as e:
            messages.error(request, f'Error creating teacher: {str(e)}')
            return self.get(request, *args, **kwargs)
class TeacherDetailView(LoginRequiredMixin, TemplateView):
    """View teacher details and assigned subjects"""
    template_name = 'courses/teacher_detail.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher_id = kwargs.get('teacher_id')
        try:
            teacher = Teacher.objects.get(teacher_id=teacher_id)
            # Get assigned subjects
            assigned_subjects = BCASubject.objects.filter(assigned_teacher=teacher)
            # Get subjects by semester for better organization
            subjects_by_semester = {}
            for subject in assigned_subjects:
                semester = subject.semester
                if semester not in subjects_by_semester:
                    subjects_by_semester[semester] = []
                subjects_by_semester[semester].append(subject)
            # Get teacher statistics - MongoDB compatible way
            total_assignments = 0
            total_materials = 0
            pending_submissions = 0
            try:
                # Count assignments created by this teacher
                all_assignments = Assignment.objects.all()
                for assignment in all_assignments:
                    if hasattr(assignment, 'created_by') and assignment.created_by == teacher:
                        total_assignments += 1
                # Count materials uploaded by this teacher  
                all_materials = CourseMaterial.objects.all()
                for material in all_materials:
                    if hasattr(material, 'uploaded_by') and material.uploaded_by == teacher:
                        total_materials += 1
                # Count pending submissions for this teacher's assignments
                all_submissions = AssignmentSubmission.objects.filter(status='submitted')
                teacher_assignments = Assignment.objects.filter(created_by=teacher)
                teacher_assignment_ids = [str(assignment.id) for assignment in teacher_assignments]
                for submission in all_submissions:
                    if hasattr(submission, 'assignment') and str(submission.assignment.id) in teacher_assignment_ids:
                        pending_submissions += 1
            except Exception as e:
                # If statistics fail, just use 0 values
                print(f"Statistics calculation error: {e}")
                total_assignments = 0
                total_materials = 0
                pending_submissions = 0
            context.update({
                'teacher': teacher,
                'assigned_subjects': assigned_subjects,
                'subjects_by_semester': subjects_by_semester,
                'total_assignments': total_assignments,
                'total_materials': total_materials,
                'pending_submissions': pending_submissions,
                'can_edit': self.request.user.role in ['admin']
            })
        except Teacher.DoesNotExist:
            messages.error(self.request, 'Teacher not found!')
            context['teacher'] = None
        except Exception as e:
            messages.error(self.request, f'Error loading teacher details: {str(e)}')
            context['teacher'] = None
        return context
class TeacherEditView(LoginRequiredMixin, TemplateView):
    """Edit teacher information and subject assignments"""
    template_name = 'courses/teacher_edit.html'
    def get_context_data(self, **kwargs):  # ✅ Fixed indentation - now inside the class
        context = super().get_context_data(**kwargs)
        teacher_id = kwargs.get('teacher_id')
        if self.request.user.role not in ['admin']:
            messages.error(self.request, 'Access denied! Only admin can edit teachers.')
            return context
        try:
            teacher = Teacher.objects.get(teacher_id=teacher_id)
            annual_salary = teacher.salary * 12 if teacher.salary else 0
            all_subjects = BCASubject.objects.all().order_by('semester', 'subject_name')
            assigned_subjects = BCASubject.objects.filter(assigned_teacher=teacher)
            assigned_subject_codes = [subject.subject_code for subject in assigned_subjects]
            context.update({
                'teacher': teacher,
                'all_subjects': all_subjects,
                'assigned_subject_codes': assigned_subject_codes,
                'departments': ['Computer Science', 'Information Technology', 'Management', 'Mathematics', 'English'],
                'designations': ['Professor', 'Associate Professor', 'Assistant Professor', 'Lecturer', 'Senior Lecturer', 'Department Head'],
                'annual_salary': annual_salary,
            })
        except Teacher.DoesNotExist:
            messages.error(self.request, 'Teacher not found!')
            context['teacher'] = None
        return context
    def post(self, request, *args, **kwargs):
        teacher_id = kwargs.get('teacher_id')
        if request.user.role not in ['admin']:
            messages.error(request, 'Access denied!')
            return redirect('courses:teacher-list')
        try:
            teacher = Teacher.objects.get(teacher_id=teacher_id)
            # Update teacher information
            teacher.department = request.POST.get('department')
            teacher.designation = request.POST.get('designation')
            # Update qualification field
            teacher.qualification = request.POST.get('qualification', '')
            # Update salary field
            salary_str = request.POST.get('salary', '').strip()
            if salary_str:
                try:
                    teacher.salary = float(salary_str)
                except ValueError:
                    teacher.salary = None
                    messages.warning(request, 'Invalid salary value. Salary was not updated.')
            else:
                teacher.salary = None
            # Update subject assignments
            new_subjects = request.POST.getlist('subjects_teaching')
            teacher.subjects_teaching = new_subjects
            teacher.updated_at = datetime.datetime.now()
            teacher.save()
            # Update subject assignments in database
            # First, remove teacher from all previously assigned subjects
            previous_subjects = BCASubject.objects.filter(assigned_teacher=teacher)
            for subject in previous_subjects:
                subject.assigned_teacher = None
                subject.save()
            # Then assign teacher to new subjects
            assigned_count = 0
            for subject_code in new_subjects:
                try:
                    subject = BCASubject.objects.get(subject_code=subject_code)
                    subject.assigned_teacher = teacher
                    subject.save()
                    assigned_count += 1
                except BCASubject.DoesNotExist:
                    continue
            # Create success message with salary information
            salary_info = ""
            if teacher.salary:
                salary_info = f" | Monthly Salary: Rs. {teacher.salary:,.2f}"
            messages.success(
                request, 
                f'Teacher {teacher.full_name} updated successfully! '
                f'Now assigned to {assigned_count} subjects.{salary_info}'
            )
            return redirect('courses:teacher-detail', teacher_id=teacher.teacher_id)
        except Teacher.DoesNotExist:
            messages.error(request, 'Teacher not found!')
            return redirect('courses:teacher-list')
        except Exception as e:
            messages.error(request, f'Error updating teacher: {str(e)}')
            return self.get(request, *args, **kwargs)
class TeacherListView(LoginRequiredMixin, TemplateView):
    """List all teachers with search and filter functionality"""
    template_name = 'courses/teacher_list.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role not in ['admin']:
            messages.error(self.request, 'Access denied! Only admin can manage teachers.')
            return context
        # Get search parameters
        search_query = self.request.GET.get('search', '')
        department_filter = self.request.GET.get('department', '')
        designation_filter = self.request.GET.get('designation', '')
        status_filter = self.request.GET.get('status', '')
        # Build filter query
        teachers = Teacher.objects.all()
        if search_query:
            teachers = teachers.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(teacher_id__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        if department_filter:
            teachers = teachers.filter(department=department_filter)
        if designation_filter:
            teachers = teachers.filter(designation=designation_filter)
        if status_filter == 'active':
            teachers = teachers.filter(is_active=True)
        elif status_filter == 'inactive':
            teachers = teachers.filter(is_active=False)
        # Pagination
        paginator = Paginator(list(teachers), 10)  # 10 teachers per page
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        # Get statistics
        total_teachers = Teacher.objects.count()
        active_teachers = Teacher.objects.filter(is_active=True).count()
        inactive_teachers = total_teachers - active_teachers
        total_assigned = len([t for t in Teacher.objects.all() if t.get_assigned_subjects().count() > 0])
        # Get unique departments and designations for filters
        departments = Teacher.objects.distinct('department')
        designations = Teacher.objects.distinct('designation')
        context.update({
            'teachers': page_obj,
            'total_teachers': total_teachers,
            'active_teachers': active_teachers,
            'inactive_teachers': inactive_teachers,
            'total_assigned': total_assigned,
            'search_query': search_query,
            'department_filter': department_filter,
            'designation_filter': designation_filter,
            'departments': departments,
            'designations': designations,
            'has_search': bool(search_query or department_filter or designation_filter or status_filter)
        })
        return context
class TeacherDeleteView(LoginRequiredMixin, TemplateView):
    """Delete teacher (admin only)"""
    def post(self, request, *args, **kwargs):
        teacher_id = kwargs.get('teacher_id')
        if request.user.role not in ['admin']:
            messages.error(request, 'Access denied!')
            return redirect('courses:teacher-list')
        try:
            teacher = Teacher.objects.get(teacher_id=teacher_id)
            teacher_name = teacher.full_name
            # Remove teacher from assigned subjects
            assigned_subjects = BCASubject.objects.filter(assigned_teacher=teacher)
            for subject in assigned_subjects:
                subject.assigned_teacher = None
                subject.save()
            # Delete teacher
            teacher.delete()
            messages.success(request, f'Teacher {teacher_name} deleted successfully!')
        except Teacher.DoesNotExist:
            messages.error(request, 'Teacher not found!')
        except Exception as e:
            messages.error(request, f'Error deleting teacher: {str(e)}')
        return redirect('courses:teacher-list')
class TeacherPasswordChangeView(LoginRequiredMixin, TemplateView):
    """Admin can change teacher passwords"""
    template_name = 'courses/teacher_password_change.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        teacher_id = kwargs.get('teacher_id')
        if self.request.user.role not in ['admin']:
            messages.error(self.request, 'Access denied! Only admin can change teacher passwords.')
            return context
        try:
            teacher = Teacher.objects.get(teacher_id=teacher_id)
            # Check if teacher has a Django user account
            try:
                django_user = User.objects.get(email=teacher.email)
                context['has_user_account'] = True
                context['user_email'] = django_user.email
            except User.DoesNotExist:
                context['has_user_account'] = False
                context['user_email'] = None
            context['teacher'] = teacher
        except Teacher.DoesNotExist:
            messages.error(self.request, 'Teacher not found!')
            context['teacher'] = None
        return context
    def post(self, request, *args, **kwargs):
        teacher_id = kwargs.get('teacher_id')
        if request.user.role not in ['admin']:
            messages.error(request, 'Access denied!')
            return redirect('courses:teacher-list')
        try:
            teacher = Teacher.objects.get(teacher_id=teacher_id)
            new_password = request.POST.get('new_password', '').strip()
            confirm_password = request.POST.get('confirm_password', '').strip()
            # Validate passwords
            if not new_password:
                messages.error(request, 'Password cannot be empty!')
                return self.get(request, *args, **kwargs)
            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match!')
                return self.get(request, *args, **kwargs)
            if len(new_password) < 6:
                messages.error(request, 'Password must be at least 6 characters long!')
                return self.get(request, *args, **kwargs)
            # Try to find and update Django user account
            try:
                # Look for existing Django user by email
                django_user = User.objects.get(email=teacher.email)
                django_user.set_password(new_password)
                django_user.save()
                messages.success(
                    request,
                    f'Password updated successfully for {teacher.full_name}! '
                    f'Login Email: {teacher.email} | New Password: {new_password} '
                    f'(Please share this password securely with the teacher)'
                )
            except User.DoesNotExist:
                # No Django user account exists, create one
                try:
                    django_user = User.objects.create_user(
                        email=teacher.email,
                        password=new_password,
                        first_name=teacher.first_name,
                        last_name=teacher.last_name,
                        role='teacher'
                    )
                    # Also create UserProfile if needed
                    try:
                        from accounts.models import UserProfile
                        user_profile = UserProfile(
                            user_id=str(django_user.id),
                            email=teacher.email,
                            first_name=teacher.first_name,
                            last_name=teacher.last_name,
                            phone=teacher.phone_number,
                            address=teacher.address,
                            date_of_birth=teacher.date_of_birth,
                            gender=teacher.gender[0] if teacher.gender else 'M',
                            role='teacher'
                        )
                        user_profile.save()
                        # Link UserProfile to Teacher
                        teacher.user_profile = user_profile
                        teacher.save()
                    except Exception as profile_error:
                        # User created but profile creation failed - that's okay
                        pass
                    messages.success(
                        request,
                        f'New user account created for {teacher.full_name}! '
                        f'Login Email: {teacher.email} | Password: {new_password} '
                        f'(Please share this password securely with the teacher)'
                    )
                except Exception as user_error:
                    messages.error(
                        request, 
                        f'Error creating user account: {str(user_error)}'
                    )
                    return self.get(request, *args, **kwargs)
            return redirect('courses:teacher-detail', teacher_id=teacher.teacher_id)
        except Teacher.DoesNotExist:
            messages.error(request, 'Teacher not found!')
            return redirect('courses:teacher-list')
        except Exception as e:
            messages.error(request, f'Error updating password: {str(e)}')
            return self.get(request, *args, **kwargs)
# ============================================================================
# TEACHER ACTIVE/INACTIVE STATUS MANAGEMENT
# ============================================================================
@login_required
def toggle_teacher_status(request, teacher_id):
    """Toggle teacher active/inactive status and refresh dashboard"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admins can change teacher status.')
        return redirect('courses:teacher-list')
    try:
        teacher = Teacher.objects.get(teacher_id=teacher_id)
        # Toggle status
        teacher.is_active = not teacher.is_active
        teacher.save()
        # Also update Django User account if exists
        try:
            user_account = User.objects.get(email=teacher.email)
            user_account.is_active = teacher.is_active
            user_account.save()
            status_text = "activated" if teacher.is_active else "deactivated"
            messages.success(request, f'Teacher {teacher.full_name} has been {status_text}.')
            if not teacher.is_active:
                messages.info(request, f'{teacher.full_name} will no longer be able to log in.')
        except User.DoesNotExist:
            status_text = "activated" if teacher.is_active else "deactivated"
            messages.success(request, f'Teacher {teacher.full_name} has been {status_text}.')
    except Teacher.DoesNotExist:
        messages.error(request, 'Teacher not found.')
    return redirect('courses:teacher-detail', teacher_id=teacher_id)
@login_required
def assign_teacher_to_subject(request):
    """Assign or reassign teacher to a subject (Admin only)"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admins can assign teachers.')
        return redirect('courses:course-management')
    if request.method == 'POST':
        subject_code = request.POST.get('subject_code')
        teacher_id = request.POST.get('teacher_id')
        try:
            # Get subject and teacher
            subject = BCASubject.objects.get(subject_code=subject_code)
            teacher = Teacher.objects.get(teacher_id=teacher_id)
            # Remove subject from previous teacher's assignments (if any)
            if subject.assigned_teacher:
                old_teacher = subject.assigned_teacher
                if subject_code in old_teacher.subjects_teaching:
                    old_teacher.subjects_teaching.remove(subject_code)
                    old_teacher.save()
            # Assign new teacher
            subject.assigned_teacher = teacher
            subject.save()
            # Add subject to teacher's teaching list
            if subject_code not in teacher.subjects_teaching:
                teacher.subjects_teaching.append(subject_code)
                teacher.save()
            messages.success(
                request, 
                f'Successfully assigned {teacher.full_name} to {subject.subject_name} ({subject_code})'
            )
        except BCASubject.DoesNotExist:
            messages.error(request, 'Subject not found!')
        except Teacher.DoesNotExist:
            messages.error(request, 'Teacher not found!')
        except Exception as e:
            messages.error(request, f'Error assigning teacher: {str(e)}')
    return redirect('courses:course-management')
# ============================================================================
# UTILITY FUNCTIONS AND API ENDPOINTS
# ============================================================================
def get_course_statistics():
    """Get statistics for simplified dashboard - Only active teachers and total courses"""
    try:
        total_subjects = BCASubject.objects.count()
        total_teachers = Teacher.objects.count()
        active_teachers = Teacher.objects.filter(is_active=True).count()
        inactive_teachers = total_teachers - active_teachers
        total_assignments = Assignment.objects.count()
        total_materials = CourseMaterial.objects.filter(is_active=True).count()
        return {
            'total_courses': total_subjects,
            'total_teachers': total_teachers,
            'active_teachers': active_teachers,
            'inactive_teachers': inactive_teachers,
            'total_assignments': total_assignments,
            'total_materials': total_materials
        }
    except Exception as e:
        return {'error': str(e)}
def course_dashboard_stats(request):
    """API endpoint for course statistics - Simplified for dashboard"""
    if request.method == 'GET':
        stats = get_course_statistics()
        return JsonResponse(stats)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
def teacher_dashboard_stats(request):
    """API endpoint for teacher statistics - Updated for simplified dashboard"""
    if request.method == 'GET':
        try:
            total_teachers = Teacher.objects.count()
            active_teachers = Teacher.objects.filter(is_active=True).count()
            inactive_teachers = total_teachers - active_teachers
            total_subjects = BCASubject.objects.count()
            assigned_subjects = BCASubject.objects.filter(assigned_teacher__ne=None).count()
            unassigned_subjects = total_subjects - assigned_subjects
            stats = {
                'total_teachers': total_teachers,
                'active_teachers': active_teachers,
                'inactive_teachers': inactive_teachers,
                'total_subjects': total_subjects,
                'assigned_subjects': assigned_subjects,
                'unassigned_subjects': unassigned_subjects
            }
            return JsonResponse(stats)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
# ============================================================================
# FILE DOWNLOAD AND VIEW FUNCTIONS
# ============================================================================
def download_assignment_file(request, assignment_id):
    """Download assignment file attached by teacher"""
    try:
        assignment = Assignment.objects.get(id=assignment_id)
        # Check if user has access to this assignment
        if request.user.role == 'student':
            # Students can only access files for assignments in their current semester
            student = Student.objects.get(email=request.user.email)
            enrollment = StudentEnrollment.objects.filter(student=student).first()
            if not enrollment or assignment.subject.semester != enrollment.current_semester:
                raise Http404("Access denied")
        elif request.user.role not in ['teacher', 'admin']:
            raise Http404("Access denied")
        # Check if assignment has a file
        if not assignment.assignment_file_path:
            raise Http404("No file attached to this assignment")
        # Get file path
        file_path = assignment.assignment_file_path
        # Check if file exists
        if not default_storage.exists(file_path):
            raise Http404("File not found")
        # Open and return file
        file_obj = default_storage.open(file_path, 'rb')
        # Get file name
        file_name = assignment.assignment_file_name or os.path.basename(file_path)
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_name)
        if not content_type:
            content_type = 'application/octet-stream'
        # Create response
        response = FileResponse(
            file_obj,
            content_type=content_type,
            as_attachment=True,
            filename=file_name
        )
        return response
    except Assignment.DoesNotExist:
        raise Http404("Assignment not found")
    except Student.DoesNotExist:
        raise Http404("Student profile not found")
    except Exception as e:
        raise Http404(f"Error downloading file: {str(e)}")
def view_assignment_file(request, assignment_id):
    """View assignment file in browser (for images/PDFs)"""
    try:
        assignment = Assignment.objects.get(id=assignment_id)
        # Check if user has access to this assignment
        if request.user.role == 'student':
            student = Student.objects.get(email=request.user.email)
            enrollment = StudentEnrollment.objects.filter(student=student).first()
            if not enrollment or assignment.subject.semester != enrollment.current_semester:
                raise Http404("Access denied")
        elif request.user.role not in ['teacher', 'admin']:
            raise Http404("Access denied")
        # Check if assignment has a file
        if not assignment.assignment_file_path:
            raise Http404("No file attached to this assignment")
        # Get file path
        file_path = assignment.assignment_file_path
        # Check if file exists
        if not default_storage.exists(file_path):
            raise Http404("File not found")
        # Open file
        file_obj = default_storage.open(file_path, 'rb')
        # Get file name and determine content type
        file_name = assignment.assignment_file_name or os.path.basename(file_path)
        content_type, _ = mimetypes.guess_type(file_name)
        if not content_type:
            content_type = 'application/octet-stream'
        # For images and PDFs, display inline; for others, download
        if content_type.startswith('image/') or content_type == 'application/pdf':
            response = FileResponse(
                file_obj,
                content_type=content_type,
                as_attachment=False,  # Display inline
                filename=file_name
            )
        else:
            # For other files, force download
            response = FileResponse(
                file_obj,
                content_type=content_type,
                as_attachment=True,
                filename=file_name
            )
        return response
    except Assignment.DoesNotExist:
        raise Http404("Assignment not found")
    except Student.DoesNotExist:
        raise Http404("Student profile not found")
    except Exception as e:
        raise Http404(f"Error viewing file: {str(e)}")
class AssignmentDetailView(LoginRequiredMixin, TemplateView):
    """Detailed view of a specific assignment"""
    template_name = 'courses/assignment_detail.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment_id = kwargs.get('assignment_id')
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            # Security check: Student can only access assignments for their semester
            if self.request.user.role == 'student':
                student = Student.objects.get(email=self.request.user.email)
                enrollment = StudentEnrollment.objects.filter(student=student).first()
                if not enrollment or assignment.subject.semester != enrollment.current_semester:
                    messages.error(self.request, 'You can only access assignments from your current semester!')
                    context['assignment'] = None
                    return context
                # Get student's submission for this assignment
                submission = AssignmentSubmission.objects.filter(
                    assignment=assignment,
                    student=student
                ).first()
                context['user_submission'] = submission
            # Get file extension for display
            file_extension = None
            file_type = None
            if assignment.assignment_file_name:
                file_extension = assignment.assignment_file_name.split('.')[-1].lower()
                if file_extension in ['jpg', 'jpeg', 'png', 'gif']:
                    file_type = 'image'
                elif file_extension == 'pdf':
                    file_type = 'pdf'
                elif file_extension in ['doc', 'docx']:
                    file_type = 'document'
                else:
                    file_type = 'other'
            context.update({
                'assignment': assignment,
                'file_extension': file_extension,
                'file_type': file_type,
                'is_teacher': self.request.user.role in ['teacher', 'admin']
            })
        except Assignment.DoesNotExist:
            messages.error(self.request, 'Assignment not found!')
            context['assignment'] = None
        except Student.DoesNotExist:
            if self.request.user.role == 'student':
                messages.error(self.request, 'Student profile not found!')
                context['assignment'] = None
        return context
class AssignmentSubmissionsView(LoginRequiredMixin, TemplateView):
    """View all submissions for an assignment (Teacher only)"""
    template_name = 'courses/assignment_submissions.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignment_id = kwargs.get('assignment_id')
        # Only teachers and admins can view submissions
        if self.request.user.role not in ['teacher', 'admin']:
            messages.error(self.request, 'Access denied!')
            return context
        try:
            assignment = Assignment.objects.get(id=assignment_id)
            # Get all submissions for this assignment
            submissions = AssignmentSubmission.objects.filter(assignment=assignment).order_by('-submission_date')
            # Get all students enrolled in this subject's semester
            enrolled_students = []
            all_students = Student.objects.all()
            for student in all_students:
                enrollment = StudentEnrollment.objects.filter(student=student).first()
                if enrollment and enrollment.current_semester == assignment.subject.semester:
                    enrolled_students.append(student)
            # Create submission status for each student
            submission_data = []
            for student in enrolled_students:
                submission = submissions.filter(student=student).first()
                submission_data.append({
                    'student': student,
                    'submission': submission,
                    'status': 'submitted' if submission else 'not_submitted',
                    'is_late': submission.is_late if submission else False,
                    'submission_date': submission.submission_date if submission else None
                })
            # Statistics
            total_students = len(enrolled_students)
            submitted_count = len([s for s in submission_data if s['submission']])
            pending_count = total_students - submitted_count
            late_submissions = len([s for s in submission_data if s['submission'] and s['is_late']])
            context.update({
                'assignment': assignment,
                'submission_data': submission_data,
                'statistics': {
                    'total_students': total_students,
                    'submitted_count': submitted_count,
                    'pending_count': pending_count,
                    'late_submissions': late_submissions,
                    'submission_rate': round((submitted_count / total_students * 100), 1) if total_students > 0 else 0
                }
            })
        except Assignment.DoesNotExist:
            messages.error(self.request, 'Assignment not found!')
            context['assignment'] = None
        return context
def download_submission_file(request, submission_id):
    """Download or view student submission file - BOTH STUDENTS AND TEACHERS CAN VIEW"""
    print(f"DEBUG: Function called with submission_id: {submission_id}")
    print(f"DEBUG: User role: {request.user.role}")
    print(f"DEBUG: User email: {request.user.email}")
    print(f"DEBUG: View parameter: {request.GET.get('view')}")
    # Allow students, teachers, and admins to view submissions
    if request.user.role not in ['teacher', 'admin', 'student']:
        print(f"DEBUG: Access denied for role: {request.user.role}")
        raise Http404("Access denied")
    try:
        submission = AssignmentSubmission.objects.get(id=submission_id)
        print(f"DEBUG: Found submission for student: {submission.student.email}")
        # Security check for students - they can only view their own submissions
        if request.user.role == 'student':
            try:
                student = Student.objects.get(email=request.user.email)
                if submission.student.id != student.id:
                    print(f"DEBUG: Student {request.user.email} tried to access submission of {submission.student.email}")
                    raise Http404("Access denied - you can only view your own submissions")
                print(f"DEBUG: Student access granted - viewing own submission")
            except Student.DoesNotExist:
                print(f"DEBUG: Student profile not found for {request.user.email}")
                raise Http404("Student profile not found")
        # Teachers and admins can view any submission
        elif request.user.role in ['teacher', 'admin']:
            print(f"DEBUG: Teacher/Admin access granted - can view any submission")
        # Check if submission has a file
        if not submission.submission_file_path:
            print("DEBUG: No file attached to this submission")
            raise Http404("No file attached to this submission")
        print(f"DEBUG: File path: {submission.submission_file_path}")
        # Check if file exists
        if not default_storage.exists(submission.submission_file_path):
            print(f"DEBUG: File not found in storage: {submission.submission_file_path}")
            raise Http404("File not found on server")
        print("DEBUG: File exists, opening...")
        # Open file
        try:
            file_obj = default_storage.open(submission.submission_file_path, 'rb')
            print("DEBUG: File opened successfully")
        except Exception as file_error:
            print(f"DEBUG: Error opening file: {file_error}")
            raise Http404(f"Error opening file: {str(file_error)}")
        # Get file name
        file_name = submission.submission_file_name
        if not file_name:
            student_id = getattr(submission.student, 'student_id', 'unknown')
            file_extension = submission.submission_file_path.split('.')[-1] if '.' in submission.submission_file_path else 'file'
            file_name = f"submission_{student_id}.{file_extension}"
        print(f"DEBUG: Using file name: {file_name}")
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_name)
        if not content_type:
            content_type = 'application/octet-stream'
        print(f"DEBUG: Content type: {content_type}")
        # Check if this is a view request
        is_view_request = request.GET.get('view') == 'true'
        print(f"DEBUG: Is view request: {is_view_request}")
        # Create response
        if is_view_request and (content_type.startswith('image/') or 
                               content_type == 'application/pdf' or 
                               content_type.startswith('text/')):
            print("DEBUG: Creating inline view response")
            response = FileResponse(
                file_obj,
                content_type=content_type,
                as_attachment=False,  # Display inline
                filename=file_name
            )
        else:
            print("DEBUG: Creating download response")
            response = FileResponse(
                file_obj,
                content_type=content_type,
                as_attachment=True,  # Force download
                filename=file_name
            )
        print("DEBUG: Response created successfully")
        return response
    except AssignmentSubmission.DoesNotExist:
        print(f"DEBUG: Submission not found with ID: {submission_id}")
        raise Http404("Submission not found")
    except Student.DoesNotExist:
        print(f"DEBUG: Student profile not found")
        raise Http404("Student profile not found")
    except Exception as e:
        print(f"DEBUG: Unexpected error: {e}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        raise Http404(f"Error accessing file: {str(e)}")
def download_material_file(request, material_id):
    """Download course material file"""
    try:
        material = CourseMaterial.objects.get(id=material_id)
        # Check if user has access to this material
        if request.user.role == 'student':
            # Students can only access materials for their current semester
            student = Student.objects.get(email=request.user.email)
            enrollment = StudentEnrollment.objects.filter(student=student).first()
            if not enrollment or material.subject.semester != enrollment.current_semester:
                raise Http404("Access denied")
        elif request.user.role not in ['teacher', 'admin']:
            raise Http404("Access denied")
        # Check if material has a file
        if not material.file_path:
            raise Http404("No file attached to this material")
        # Get file path
        file_path = material.file_path
        # Check if file exists
        if not default_storage.exists(file_path):
            raise Http404("File not found")
        # Open and return file
        file_obj = default_storage.open(file_path, 'rb')
        # Get file name
        file_name = material.file_name or os.path.basename(file_path)
        # Determine content type
        content_type, _ = mimetypes.guess_type(file_name)
        if not content_type:
            content_type = 'application/octet-stream'
        # Create response
        response = FileResponse(
            file_obj,
            content_type=content_type,
            as_attachment=True,
            filename=file_name
        )
        return response
    except CourseMaterial.DoesNotExist:
        raise Http404("Material not found")
    except Student.DoesNotExist:
        raise Http404("Student profile not found")
    except Exception as e:
        raise Http404(f"Error downloading file: {str(e)}")
def view_material_file(request, material_id):
    """View course material file in browser (for images/PDFs)"""
    try:
        material = CourseMaterial.objects.get(id=material_id)
        # Check if user has access to this material
        if request.user.role == 'student':
            student = Student.objects.get(email=request.user.email)
            enrollment = StudentEnrollment.objects.filter(student=student).first()
            if not enrollment or material.subject.semester != enrollment.current_semester:
                raise Http404("Access denied")
        elif request.user.role not in ['teacher', 'admin']:
            raise Http404("Access denied")
        # Check if material has a file
        if not material.file_path:
            raise Http404("No file attached to this material")
        # Get file path
        file_path = material.file_path
        # Check if file exists
        if not default_storage.exists(file_path):
            raise Http404("File not found")
        # Open file
        file_obj = default_storage.open(file_path, 'rb')
        # Get file name and determine content type
        file_name = material.file_name or os.path.basename(file_path)
        content_type, _ = mimetypes.guess_type(file_name)
        if not content_type:
            content_type = 'application/octet-stream'
        # For images and PDFs, display inline; for others, download
        if content_type.startswith('image/') or content_type == 'application/pdf':
            response = FileResponse(
                file_obj,
                content_type=content_type,
                as_attachment=False,  # Display inline
                filename=file_name
            )
        else:
            # For other files, force download
            response = FileResponse(
                file_obj,
                content_type=content_type,
                as_attachment=True,
                filename=file_name
            )
        return response
    except CourseMaterial.DoesNotExist:
        raise Http404("Material not found")
    except Student.DoesNotExist:
        raise Http404("Student profile not found")
    except Exception as e:
        raise Http404(f"Error viewing file: {str(e)}")
class StudentAssignmentsView(LoginRequiredMixin, TemplateView):
    """Student view of all their assignments across subjects"""
    template_name = 'courses/student_assignments.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role != 'student':
            messages.error(self.request, 'Access denied!')
            return context
        try:
            # Get student profile
            student = Student.objects.filter(email=self.request.user.email).first()
            if not student:
                messages.warning(self.request, 'Student profile not found.')
                context['student'] = None
                return context
            # Get student enrollment
            enrollment = StudentEnrollment.objects.filter(student=student).first()
            if not enrollment:
                messages.warning(self.request, 'Enrollment information not found.')
                context['student'] = student
                return context
            # Get subjects for current semester
            semester_subjects = BCASubject.objects.filter(semester=enrollment.current_semester)
            # Get all assignments for current semester subjects - ONLY THOSE CREATED AFTER STUDENT ENROLLMENT
            all_assignments = Assignment.objects.filter(
                subject__in=semester_subjects,
                created_date__gte=student.created_at  # Only assignments created after student joined
            ).order_by('-created_date')
            
            print(f"STUDENT ASSIGNMENTS FILTER: Student {student.full_name} sees {all_assignments.count()} assignments (created after {student.created_at})")
            # Get student's submissions
            student_submissions = AssignmentSubmission.objects.filter(
                student=student,
                assignment__in=all_assignments
            )
            # Create submission lookup for easy template access
            submissions_dict = {}
            for submission in student_submissions:
                submissions_dict[str(submission.assignment.id)] = submission
            # Categorize assignments with detailed pending assignments
            pending_assignments = []  # Detailed list for pending assignments section
            pending_assignments_count = 0
            submitted_assignments = []
            overdue_assignments = []
            graded_assignments = []
            
            for assignment in all_assignments:
                assignment_data = {
                    'assignment': assignment,
                    'subject': assignment.subject,
                    'submission': submissions_dict.get(str(assignment.id)),
                    'days_remaining': assignment.days_remaining,
                    'is_overdue': assignment.is_overdue,
                    'is_urgent': assignment.days_remaining <= 3,  # Mark as urgent if due in 3 days or less
                    'due_date': assignment.due_date
                }
                submission = submissions_dict.get(str(assignment.id))
                
                if submission:
                    if submission.status == 'graded':
                        graded_assignments.append(assignment_data)
                    else:
                        submitted_assignments.append(assignment_data)
                elif assignment.is_overdue:
                    overdue_assignments.append(assignment_data)
                else:
                    pending_assignments_count += 1  # Count instead of append
                    pending_assignments.append(assignment_data)  # Add to list for template
                    print(f"DEBUG: StudentAssignmentsView - Assignment '{assignment_data['assignment'].title}' - PENDING (not submitted, not overdue)")
            # Calculate statistics
            total_assignments = all_assignments.count()
            submitted_count = len(submitted_assignments) + len(graded_assignments)
            pending_count = len(pending_assignments)  # Get the count from the list
            overdue_count = len(overdue_assignments)
            graded_count = len(graded_assignments)
            # Calculate submission rate
            submission_rate = round((submitted_count / total_assignments * 100), 1) if total_assignments > 0 else 0
            context.update({
                'student': student,
                'enrollment': enrollment,
                'semester_subjects': semester_subjects,
                'all_assignments': all_assignments,
                'pending_assignments': pending_assignments,
                'submitted_assignments': submitted_assignments,
                'overdue_assignments': overdue_assignments,
                'graded_assignments': graded_assignments,
                'submissions_dict': submissions_dict,
                # Statistics
                'total_assignments': total_assignments,
                'submitted_count': submitted_count,
                'pending_count': pending_count,
                'overdue_count': overdue_count,
                'graded_count': graded_count,
                'submission_rate': submission_rate,
            })
        except Exception as e:
            messages.error(self.request, f'Error loading assignments: {str(e)}')
            print(f"DEBUG: Error in StudentAssignmentsView: {str(e)}")
            context['student'] = None
        return context
# ============================================================================
# MAIN DASHBOARD ROUTER
# ============================================================================
class CourseHomeView(LoginRequiredMixin, TemplateView):
    """Route to appropriate dashboard based on user role - FIXED"""
    def get(self, request, *args, **kwargs):
        if request.user.role == 'student':
            return redirect('courses:student-dashboard')
        elif request.user.role == 'teacher':
            return redirect('courses:teacher-dashboard')
        elif request.user.role == 'admin':
            return redirect('courses:course-management')  # ← FIXED: Admin goes to course management
        else:
            messages.error(request, 'Unknown user role!')
            return redirect('dashboard')
# ============================================================================
# COURSE MANAGEMENT VIEW
# ============================================================================
class CourseManagementView(LoginRequiredMixin, TemplateView):
    """Course management - Teachers can VIEW, only Admins can EDIT"""
    template_name = 'courses/course_management.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # FIXED: Allow both teachers and admins to access
        if self.request.user.role not in ['admin', 'teacher']:
            messages.error(self.request, 'Access denied! Only admin and teachers can view courses.')
            return context
        # Determine permissions based on role
        is_admin = self.request.user.role == 'admin'
        is_teacher = self.request.user.role == 'teacher'
        # Get search parameters
        search_query = self.request.GET.get('search', '')
        semester_filter = self.request.GET.get('semester', '')
        teacher_filter = self.request.GET.get('teacher', '')
        assignment_filter = self.request.GET.get('assignment_status', '')
        # Get all BCA subjects
        subjects = BCASubject.objects.all()
        # Apply search filter
        if search_query:
            subjects = subjects.filter(
                Q(subject_name__icontains=search_query) |
                Q(subject_code__icontains=search_query)
            )
        # Apply semester filter
        if semester_filter:
            subjects = subjects.filter(semester=int(semester_filter))
        # Apply teacher filter
        if teacher_filter:
            if teacher_filter == 'assigned':
                subjects = subjects.filter(assigned_teacher__ne=None)
            elif teacher_filter == 'unassigned':
                subjects = subjects.filter(assigned_teacher=None)
        # Organize subjects by semester
        subjects_by_semester = {}
        for semester in range(1, 9):  # BCA has 8 semesters
            semester_subjects = subjects.filter(semester=semester).order_by('subject_code')
            # Add assignment and material counts for each subject
            processed_subjects = []
            for subject in semester_subjects:
                # Safely count assignments and materials
                assignment_count = 0
                material_count = 0
                try:
                    # Count assignments for this subject
                    assignment_count = Assignment.objects.filter(subject=subject).count()
                    # Count materials for this subject
                    material_count = CourseMaterial.objects.filter(subject=subject, is_active=True).count()
                except:
                    pass
                # Safely handle teacher assignment (fix broken references)
                has_teacher = False
                teacher_name = 'Not Assigned'
                try:
                    if hasattr(subject, 'assigned_teacher') and subject.assigned_teacher:
                        # Try to access teacher - this will fail if reference is broken
                        teacher = subject.assigned_teacher
                        teacher_name = f"{teacher.first_name} {teacher.last_name}"
                        has_teacher = True
                except Exception as e:
                    # Broken teacher reference - clean it up
                    print(f"DEBUG: Broken teacher reference for subject {subject.subject_code}: {e}")
                    try:
                        subject.assigned_teacher = None
                        subject.save()
                        print(f"DEBUG: Cleaned broken teacher reference for {subject.subject_code}")
                    except:
                        pass
                    has_teacher = False
                    teacher_name = 'Reference Error (Fixed)'
                # Create safe subject data
                subject_data = {
                    'subject': subject,
                    'assignment_count': assignment_count,
                    'material_count': material_count,
                    'has_teacher': has_teacher,
                    'teacher_name': teacher_name
                }
                processed_subjects.append(subject_data)
            if processed_subjects:  # Only add semesters that have subjects
                subjects_by_semester[semester] = processed_subjects
        # Get all teachers for assignment dropdown (only for admins)
        all_teachers = Teacher.objects.filter(is_active=True).order_by('first_name', 'last_name') if is_admin else []
        # Calculate statistics (safely handle broken references)
        total_subjects = BCASubject.objects.count()
        # Safely count assigned subjects
        assigned_subjects = 0
        all_subjects_for_count = BCASubject.objects.all()
        for subject in all_subjects_for_count:
            try:
                if hasattr(subject, 'assigned_teacher') and subject.assigned_teacher:
                    # Try to access teacher to verify reference is valid
                    teacher = subject.assigned_teacher
                    assigned_subjects += 1
            except:
                # Broken reference - skip counting
                continue
        unassigned_subjects = total_subjects - assigned_subjects
        total_teachers = Teacher.objects.filter(is_active=True).count()
        total_assignments = Assignment.objects.count()
        total_materials = CourseMaterial.objects.filter(is_active=True).count()
        context.update({
            'subjects_by_semester': subjects_by_semester,
            'all_teachers': all_teachers,
            'search_query': search_query,
            'semester_filter': semester_filter,
            'teacher_filter': teacher_filter,
            # Permission flags - NEW
            'is_admin': is_admin,
            'is_teacher': is_teacher,
            'can_edit': is_admin,  # Only admins can edit
            'can_view': True,      # Both can view
            # Statistics
            'total_subjects': total_subjects,
            'assigned_subjects': assigned_subjects,
            'unassigned_subjects': unassigned_subjects,
            'total_teachers': total_teachers,
            'total_assignments': total_assignments,
            'total_materials': total_materials,
            # Assignment rate
            'assignment_rate': round((assigned_subjects / total_subjects * 100), 1) if total_subjects > 0 else 0,
            # Filter status
            'has_search': bool(search_query or semester_filter or teacher_filter or assignment_filter)
        })
        return context
    # Add these views to your existing views.py file
@login_required
def approve_submission(request, submission_id):
    """Approve a student submission"""
    if request.user.role not in ['teacher', 'admin']:
        messages.error(request, 'Access denied!')
        return JsonResponse({'error': 'Access denied'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        submission = AssignmentSubmission.objects.get(id=submission_id)
        teacher = Teacher.objects.get(email=request.user.email)
        # Get optional comments
        comments = request.POST.get('comments', '').strip()
        # Approve the submission
        submission.approve(teacher, comments)
        messages.success(request, f'Submission by {submission.student.first_name} {submission.student.last_name} has been approved!')
        return JsonResponse({
            'success': True,
            'message': 'Submission approved successfully!',
            'new_status': 'approved'
        })
    except AssignmentSubmission.DoesNotExist:
        return JsonResponse({'error': 'Submission not found'}, status=404)
    except Teacher.DoesNotExist:
        return JsonResponse({'error': 'Teacher profile not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
def reject_submission(request, submission_id):
    """Reject a student submission with feedback"""
    if request.user.role not in ['teacher', 'admin']:
        messages.error(request, 'Access denied!')
        return JsonResponse({'error': 'Access denied'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        submission = AssignmentSubmission.objects.get(id=submission_id)
        teacher = Teacher.objects.get(email=request.user.email)
        # Get required reason and optional feedback
        reason = request.POST.get('reason', '').strip()
        feedback = request.POST.get('feedback', '').strip()
        if not reason:
            return JsonResponse({'error': 'Rejection reason is required'}, status=400)
        # Reject the submission
        submission.reject(teacher, reason, feedback)
        messages.success(request, f'Submission by {submission.student.first_name} {submission.student.last_name} has been rejected!')
        return JsonResponse({
            'success': True,
            'message': 'Submission rejected with feedback!',
            'new_status': 'rejected'
        })
    except AssignmentSubmission.DoesNotExist:
        return JsonResponse({'error': 'Submission not found'}, status=404)
    except Teacher.DoesNotExist:
        return JsonResponse({'error': 'Teacher profile not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
def submission_feedback_view(request, submission_id):
    """View detailed feedback for a submission (for students)"""
    try:
        submission = AssignmentSubmission.objects.get(id=submission_id)
        # Security check: students can only view their own submissions
        if request.user.role == 'student':
            student = Student.objects.get(email=request.user.email)
            if submission.student.id != student.id:
                messages.error(request, 'Access denied!')
                return redirect('courses:student-dashboard')
        elif request.user.role not in ['teacher', 'admin']:
            messages.error(request, 'Access denied!')
            return redirect('dashboard')
        context = {
            'submission': submission,
            'assignment': submission.assignment,
            'student': submission.student,
            'is_teacher': request.user.role in ['teacher', 'admin']
        }
        return render(request, 'courses/submission_feedback.html', context)
    except AssignmentSubmission.DoesNotExist:
        messages.error(request, 'Submission not found!')
        return redirect('courses:student-dashboard')
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found!')
        return redirect('courses:student-dashboard')
# Add this to your courses/views.py
@login_required
def download_my_submission(request, assignment_id):
    """Allow students to download their own submission file"""
    if request.user.role != 'student':
        raise Http404("Access denied - Students only")
    try:
        # Get the student
        student = Student.objects.get(email=request.user.email)
        # Get the assignment
        assignment = Assignment.objects.get(id=assignment_id)
        # Security check: Student can only access their semester subjects
        enrollment = StudentEnrollment.objects.filter(student=student).first()
        if not enrollment or assignment.subject.semester != enrollment.current_semester:
            raise Http404("Access denied - Subject not in your current semester")
        # Get the student's submission for this assignment
        submission = AssignmentSubmission.objects.filter(
            assignment=assignment,
            student=student
        ).first()
        if not submission:
            raise Http404("No submission found for this assignment")
        if not submission.submission_file_path:
            raise Http404("No file attached to your submission")
        # Check if file exists
        if not default_storage.exists(submission.submission_file_path):
            raise Http404("Submission file not found on server")
        # Open and return file
        file_obj = default_storage.open(submission.submission_file_path, 'rb')
        # Get file name
        original_name = submission.submission_file_name
        if not original_name:
            # Generate a meaningful filename
            file_extension = submission.submission_file_path.split('.')[-1] if '.' in submission.submission_file_path else 'file'
            original_name = f"{assignment.title}_{student.student_id}_submission.{file_extension}"
        # Determine content type
        content_type, _ = mimetypes.guess_type(original_name)
        if not content_type:
            content_type = 'application/octet-stream'
        # Check if this is a view request (open in browser)
        is_view_request = request.GET.get('view') == 'true'
        if is_view_request and (content_type.startswith('image/') or 
                               content_type == 'application/pdf' or 
                               content_type.startswith('text/')):
            # Display in browser
            response = FileResponse(
                file_obj,
                content_type=content_type,
                as_attachment=False,
                filename=original_name
            )
        else:
            # Force download
            response = FileResponse(
                file_obj,
                content_type=content_type,
                as_attachment=True,
                filename=original_name
            )
        return response
    except Student.DoesNotExist:
        raise Http404("Student profile not found")
    except Assignment.DoesNotExist:
        raise Http404("Assignment not found")
    except Exception as e:
        print(f"DEBUG: Error in download_my_submission: {e}")
        raise Http404(f"Error downloading file: {str(e)}")
@login_required 
def view_my_submission(request, assignment_id):
    """Allow students to view their own submission file in browser"""
    # Redirect to download with view parameter
    return redirect(f"{reverse('courses:download-my-submission', args=[assignment_id])}?view=true")
@login_required
@require_http_methods(["POST"])
def edit_material(request, material_id):
    """Edit course material (teacher only)"""
    if request.user.role not in ['teacher', 'admin']:
        return JsonResponse({'error': 'Access denied'}, status=403)
    try:
        material = CourseMaterial.objects.get(id=material_id)
        # Check if teacher owns this material or is admin
        if request.user.role == 'teacher':
            teacher = Teacher.objects.get(email=request.user.email)
            if material.uploaded_by.id != teacher.id:
                return JsonResponse({'error': 'You can only edit materials you uploaded'}, status=403)
        # Parse JSON data
        data = json.loads(request.body)
        # Update material
        material.title = data.get('title', '').strip()
        material.description = data.get('description', '').strip()
        material.save()
        return JsonResponse({
            'success': True,
            'message': 'Material updated successfully',
            'material': {
                'id': str(material.id),
                'title': material.title,
                'description': material.description
            }
        })
    except CourseMaterial.DoesNotExist:
        return JsonResponse({'error': 'Material not found'}, status=404)
    except Teacher.DoesNotExist:
        return JsonResponse({'error': 'Teacher profile not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
@require_http_methods(["POST"])
def delete_material(request, material_id):
    """Delete course material (teacher only)"""
    if request.user.role not in ['teacher', 'admin']:
        return JsonResponse({'error': 'Access denied'}, status=403)
    try:
        material = CourseMaterial.objects.get(id=material_id)
        # Check if teacher owns this material or is admin
        if request.user.role == 'teacher':
            teacher = Teacher.objects.get(email=request.user.email)
            if material.uploaded_by.id != teacher.id:
                return JsonResponse({'error': 'You can only delete materials you uploaded'}, status=403)
        # Delete the file from storage
        if material.file_path and default_storage.exists(material.file_path):
            default_storage.delete(material.file_path)
        # Delete the material record
        material_title = material.title
        material.delete()
        return JsonResponse({
            'success': True,
            'message': f'Material "{material_title}" deleted successfully'
        })
    except CourseMaterial.DoesNotExist:
        return JsonResponse({'error': 'Material not found'}, status=404)
    except Teacher.DoesNotExist:
        return JsonResponse({'error': 'Teacher profile not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
@require_http_methods(["POST"])
def edit_assignment(request, assignment_id):
    """Edit assignment (teacher only)"""
    if request.user.role not in ['teacher', 'admin']:
        return JsonResponse({'error': 'Access denied'}, status=403)
    try:
        assignment = Assignment.objects.get(id=assignment_id)
        # Check if teacher owns this assignment or is admin
        if request.user.role == 'teacher':
            teacher = Teacher.objects.get(email=request.user.email)
            if str(assignment.created_by.id) != str(teacher.id):
                return JsonResponse({'error': 'You can only edit assignments you created'}, status=403)
        # Parse JSON data
        data = json.loads(request.body)
        # Update assignment
        assignment.title = data.get('title', '').strip()
        assignment.description = data.get('description', '').strip()
        # Parse due date
        due_date_str = data.get('due_date', '')
        if due_date_str:
            try:
                assignment.due_date = datetime.datetime.fromisoformat(due_date_str.replace('Z', '+00:00'))
            except ValueError:
                return JsonResponse({'error': 'Invalid due date format'}, status=400)
        assignment.save()
        return JsonResponse({
            'success': True,
            'message': 'Assignment updated successfully',
            'assignment': {
                'id': str(assignment.id),
                'title': assignment.title,
                'description': assignment.description,
                'due_date': assignment.due_date.isoformat(),
            }
        })
    except Assignment.DoesNotExist:
        return JsonResponse({'error': 'Assignment not found'}, status=404)
    except Teacher.DoesNotExist:
        return JsonResponse({'error': 'Teacher profile not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except ValueError as e:
        return JsonResponse({'error': f'Invalid data: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
@require_http_methods(["POST"])
def delete_assignment(request, assignment_id):
    """Delete assignment and all its submissions (teacher only)"""
    if request.user.role not in ['teacher', 'admin']:
        return JsonResponse({'error': 'Access denied'}, status=403)
    try:
        assignment = Assignment.objects.get(id=assignment_id)
        # Check if teacher owns this assignment or is admin
        if request.user.role == 'teacher':
            teacher = Teacher.objects.get(email=request.user.email)
            if str(assignment.created_by.id) != str(teacher.id):
                return JsonResponse({'error': 'You can only delete assignments you created'}, status=403)
        # Get all submissions for this assignment
        submissions = AssignmentSubmission.objects.filter(assignment=assignment)
        # Delete submission files from storage
        for submission in submissions:
            if submission.submission_file_path and default_storage.exists(submission.submission_file_path):
                try:
                    default_storage.delete(submission.submission_file_path)
                except Exception as e:
                    print(f"Error deleting submission file: {e}")
        # Delete assignment file from storage
        if assignment.assignment_file_path and default_storage.exists(assignment.assignment_file_path):
            try:
                default_storage.delete(assignment.assignment_file_path)
            except Exception as e:
                print(f"Error deleting assignment file: {e}")
        # Delete all submissions
        submissions.delete()
        # Delete the assignment
        assignment_title = assignment.title
        assignment.delete()
        return JsonResponse({
            'success': True,
            'message': f'Assignment "{assignment_title}" and all its submissions deleted successfully'
        })
    except Assignment.DoesNotExist:
        return JsonResponse({'error': 'Assignment not found'}, status=404)
    except Teacher.DoesNotExist:
        return JsonResponse({'error': 'Teacher profile not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
class StudentFeeManagementView(LoginRequiredMixin, TemplateView):
    """Manage student fee payments"""
    template_name = 'courses/student_fee_management.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role != 'admin':
            messages.error(self.request, 'Access denied! Only admins can manage fees.')
            return context
        # Get search parameters
        search_query = self.request.GET.get('search', '')
        semester_filter = self.request.GET.get('semester', '')
        status_filter = self.request.GET.get('status', '')
        # Get all students with their fee records
        students = Student.objects.filter(is_active=True).order_by('student_id')
        if search_query:
            students = students.filter(
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(student_id__icontains=search_query)
            )
        # Prepare student fee data
        student_fee_data = []
        total_expected_revenue = 0
        total_collected_revenue = 0
        for student in students:
            # Get or create fee records for all semesters up to current
            max_semester = min(student.current_semester, 8)
            student_fees = []
            student_total_paid = 0
            student_total_expected = max_semester * 50000
            for sem in range(1, max_semester + 1):
                fee_record = StudentFeeRecord.objects.filter(
                    student=student, semester=sem
                ).first()
                if not fee_record:
                    # Auto-create fee record
                    fee_record = StudentFeeRecord(
                        student=student,
                        semester=sem,
                        total_fee=50000.0
                    )
                    fee_record.save()
                student_fees.append(fee_record)
                student_total_paid += fee_record.paid_amount
            # Apply filters
            if semester_filter:
                semester_fees = [f for f in student_fees if f.semester == int(semester_filter)]
                if not semester_fees:
                    continue
            if status_filter:
                if status_filter == 'pending':
                    if student_total_paid >= student_total_expected:
                        continue
                elif status_filter == 'completed':
                    if student_total_paid < student_total_expected:
                        continue
            student_fee_data.append({
                'student': student,
                'fee_records': student_fees,
                'total_paid': student_total_paid,
                'total_expected': student_total_expected,
                'completion_percentage': round((student_total_paid / student_total_expected * 100), 1) if student_total_expected > 0 else 0
            })
            total_expected_revenue += student_total_expected
            total_collected_revenue += student_total_paid
        context.update({
            'student_fee_data': student_fee_data,
            'total_students': len(student_fee_data),
            'total_expected_revenue': total_expected_revenue,
            'total_collected_revenue': total_collected_revenue,
            'collection_percentage': round((total_collected_revenue / total_expected_revenue * 100), 1) if total_expected_revenue > 0 else 0,
            'search_query': search_query,
            'semester_filter': semester_filter,
            'status_filter': status_filter,
        })
        return context
@login_required
def mark_fee_payment(request):
    """Mark fee payment for student"""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)
    if request.method == 'POST':
        try:
            student_id = request.POST.get('student_id')
            semester = int(request.POST.get('semester'))
            amount_paid = float(request.POST.get('amount_paid', 0))
            payment_method = request.POST.get('payment_method', 'cash')
            notes = request.POST.get('notes', '')
            # Validate amount
            if amount_paid <= 0:
                return JsonResponse({'error': 'Amount must be greater than 0'}, status=400)
            if amount_paid > 50000:
                return JsonResponse({'error': 'Amount cannot exceed Rs.50,000 per semester'}, status=400)
            # Get student
            student = Student.objects.get(id=student_id)
            # Get or create fee record
            fee_record = StudentFeeRecord.objects.filter(
                student=student, semester=semester
            ).first()
            if not fee_record:
                fee_record = StudentFeeRecord(
                    student=student,
                    semester=semester,
                    total_fee=50000.0
                )
            # CHECK FOR OVERPAYMENT - Prevent paying more than remaining balance
            remaining_balance = fee_record.total_fee - fee_record.paid_amount
            if remaining_balance <= 0:
                return JsonResponse({
                    'error': f'This semester is already fully paid (Rs.{fee_record.paid_amount:.2f}/Rs.{fee_record.total_fee:.2f})'
                }, status=400)
            if amount_paid > remaining_balance:
                return JsonResponse({
                    'error': f'Payment amount (Rs.{amount_paid:.2f}) exceeds remaining balance (Rs.{remaining_balance:.2f}). Please enter Rs.{remaining_balance:.2f} or less.'
                }, status=400)
            # Update payment details
            fee_record.paid_amount += amount_paid
            fee_record.payment_method = payment_method
            fee_record.notes = notes
            fee_record.payment_date = datetime.datetime.now()
            # Get admin profile
            try:
                from accounts.models import UserProfile
                admin_profile = UserProfile.objects.filter(user_id=str(request.user.id)).first()
                if admin_profile:
                    fee_record.recorded_by = admin_profile
            except:
                pass
            fee_record.save()  # This will auto-update status and completion
            # Calculate new remaining balance
            new_remaining = fee_record.total_fee - fee_record.paid_amount
            return JsonResponse({
                'success': True,
                'message': f'Payment of Rs.{amount_paid:.2f} recorded successfully! Remaining balance: Rs.{new_remaining:.2f}',
                'new_status': fee_record.payment_status,
                'is_completed': fee_record.is_completed,
                'remaining_amount': new_remaining,
                'total_paid': fee_record.paid_amount,
                'completion_percentage': round((fee_record.paid_amount / fee_record.total_fee * 100), 1)
            })
        except Student.DoesNotExist:
            return JsonResponse({'error': 'Student not found'}, status=404)
        except ValueError as e:
            return JsonResponse({'error': f'Invalid data format: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
# NEW: Add this view for payment history
@login_required
def student_payment_history(request, student_id):
    """Get payment history for a student"""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)
    try:
        student = Student.objects.get(id=student_id)
        fee_records = StudentFeeRecord.objects.filter(student=student).order_by('-payment_date', 'semester')
        payments = []
        total_paid = 0
        for record in fee_records:
            if record.paid_amount > 0:
                payments.append({
                    'semester': record.semester,
                    'paid_amount': record.paid_amount,
                    'payment_method': record.payment_method,
                    'payment_date': record.payment_date.isoformat() if record.payment_date else None,
                    'notes': record.notes
                })
                total_paid += record.paid_amount
        return JsonResponse({
            'success': True,
            'payments': payments,
            'student_name': student.full_name,
            'total_paid': total_paid
        })
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
# ============================================================================
# TEACHER SALARY MANAGEMENT VIEWS
# ============================================================================
class TeacherSalaryManagementView(LoginRequiredMixin, TemplateView):
    """Manage teacher salary payments"""
    template_name = 'courses/teacher_salary_management.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.role != 'admin':
            messages.error(self.request, 'Access denied! Only admins can manage salaries.')
            return context
        # Get current month/year or from parameters
        current_date = datetime.datetime.now()
        selected_month = int(self.request.GET.get('month', current_date.month))
        selected_year = int(self.request.GET.get('year', current_date.year))
        # Get all active teachers
        teachers = Teacher.objects.filter(is_active=True).order_by('teacher_id')
        # Get salary records for selected month/year
        teacher_salary_data = []
        total_salary_expense = 0
        total_paid_salary = 0
        for teacher in teachers:
            if not teacher.salary:
                continue  # Skip teachers without salary set
            # Get or create salary record
            salary_record = TeacherSalaryRecord.objects.filter(
                teacher=teacher, month=selected_month, year=selected_year
            ).first()
            if not salary_record:
                # Auto-create salary record
                salary_record = TeacherSalaryRecord(
                    teacher=teacher,
                    month=selected_month,
                    year=selected_year,
                    base_salary=teacher.salary,
                    net_salary=teacher.salary
                )
                salary_record.save()
            teacher_salary_data.append({
                'teacher': teacher,
                'salary_record': salary_record
            })
            total_salary_expense += salary_record.net_salary
            if salary_record.is_paid:
                total_paid_salary += salary_record.net_salary
        # Generate month/year options
        months = [
            (i, datetime.datetime(2000, i, 1).strftime('%B')) 
            for i in range(1, 13)
        ]
        years = list(range(2020, current_date.year + 2))
        context.update({
            'teacher_salary_data': teacher_salary_data,
            'selected_month': selected_month,
            'selected_year': selected_year,
            'selected_month_name': datetime.datetime(selected_year, selected_month, 1).strftime('%B %Y'),
            'total_teachers': len(teacher_salary_data),
            'total_salary_expense': total_salary_expense,
            'total_paid_salary': total_paid_salary,
            'payment_percentage': round((total_paid_salary / total_salary_expense * 100), 1) if total_salary_expense > 0 else 0,
            'months': months,
            'years': years,
        })
        return context
@login_required
def mark_salary_payment(request):
    """Mark salary payment for teacher"""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)
    if request.method == 'POST':
        try:
            salary_record_id = request.POST.get('salary_record_id')
            payment_method = request.POST.get('payment_method', 'bank_transfer')
            bonus = float(request.POST.get('bonus', 0))
            deductions = float(request.POST.get('deductions', 0))
            notes = request.POST.get('notes', '')
            salary_record = TeacherSalaryRecord.objects.get(id=salary_record_id)
            # Update payment details
            salary_record.bonus = bonus
            salary_record.deductions = deductions
            salary_record.payment_method = payment_method
            salary_record.notes = notes  # Store notes
            salary_record.payment_date = datetime.datetime.now()
            salary_record.payment_status = 'paid'
            # Get admin profile
            try:
                from accounts.models import UserProfile
                admin_profile = UserProfile.objects.filter(user_id=str(request.user.id)).first()
                if admin_profile:
                    salary_record.processed_by = admin_profile
            except:
                pass
            salary_record.save()  # This will auto-update net_salary and is_paid
            return JsonResponse({
                'success': True,
                'message': f'Salary payment of Rs.{salary_record.net_salary:,.2f} recorded successfully!',
                'new_status': salary_record.payment_status,
                'is_paid': salary_record.is_paid,
                'net_salary': salary_record.net_salary
            })
        except TeacherSalaryRecord.DoesNotExist:
            return JsonResponse({'error': 'Salary record not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
# NEW: Add this view for teacher salary history
@login_required
def teacher_salary_history(request, teacher_id):
    """Get salary history for a teacher"""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)
    try:
        teacher = Teacher.objects.get(id=teacher_id)
        salary_records = TeacherSalaryRecord.objects.filter(teacher=teacher).order_by('-year', '-month')
        salaries = []
        total_paid = 0
        for record in salary_records:
            if record.is_paid:
                month_names = [
                    '', 'January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December'
                ]
                salaries.append({
                    'month': record.month,
                    'year': record.year,
                    'month_name': month_names[record.month],
                    'base_salary': record.base_salary,
                    'bonus': record.bonus,
                    'deductions': record.deductions,
                    'net_salary': record.net_salary,
                    'payment_method': record.payment_method,
                    'payment_date': record.payment_date.isoformat() if record.payment_date else None,
                    'notes': record.notes
                })
                total_paid += record.net_salary
        return JsonResponse({
            'success': True,
            'salaries': salaries,
            'teacher_name': teacher.full_name,
            'total_paid': total_paid
        })
    except Teacher.DoesNotExist:
        return JsonResponse({'error': 'Teacher not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
@login_required
def generate_monthly_salaries(request):
    """Generate salary records for all teachers for a specific month"""
    if request.user.role != 'admin':
        return JsonResponse({'error': 'Access denied'}, status=403)
    if request.method == 'POST':
        try:
            month = int(request.POST.get('month'))
            year = int(request.POST.get('year'))
            created_count = TeacherSalaryRecord.generate_monthly_records(month, year)
            month_name = datetime.datetime(year, month, 1).strftime('%B %Y')
            return JsonResponse({
                'success': True,
                'message': f'Generated {created_count} salary records for {month_name}',
                'created_count': created_count
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
# ============================================================================
# LEGACY VIEWS FOR COMPATIBILITY
# ============================================================================
# Legacy views for compatibility with existing URLs
CourseListView = CourseHomeView
# CourseCreateView = TeacherDashboardView  # ← Comment this out
class CourseCreateView(LoginRequiredMixin, TemplateView):
    template_name = "courses/create.html"
class CourseDetailView(LoginRequiredMixin, TemplateView):
    template_name = "courses/detail.html"  # create this template or reuse an existing one
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["course_code"] = kwargs.get("course_code")
        return ctx
class CourseEditView(LoginRequiredMixin, TemplateView):
    template_name = "courses/edit.html"    # create this template or reuse an existing one
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["course_code"] = kwargs.get("course_code")
        return ctx
def enroll_students(request, course_code):
    # For demo only; replace with real logic later
    raise Http404("Demo only – enroll view not implemented.")
class TeacherQuickAddView(LoginRequiredMixin, TemplateView):
    template_name = "courses/teacher_quick_add.html"  # create if you want a demo screen
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject_code = kwargs.get('subject_code')
        # Check if user is teacher or admin
        if self.request.user.role not in ['teacher', 'admin']:
            messages.error(self.request, 'Access denied! Only teachers and admins can view submissions.')
            return context
        try:
            # Get the subject
            subject = BCASubject.objects.get(subject_code=subject_code)
            # Check if teacher is assigned to this subject (unless admin)
            if self.request.user.role == 'teacher':
                teacher = Teacher.objects.filter(email=self.request.user.email).first()
                if not teacher or subject.assigned_teacher != teacher:
                    messages.error(self.request, 'You can only view submissions for subjects assigned to you.')
                    return context
            # Get filter status from URL parameters
            status_filter = self.request.GET.get('status', 'all')
            # Get all assignments for this subject
            assignments = Assignment.objects.filter(subject=subject).order_by('-created_date')
            # Get all submissions for these assignments
            all_submissions = AssignmentSubmission.objects.filter(
                assignment__in=assignments
            ).order_by('-submitted_date')
            # Filter submissions based on status
            if status_filter == 'pending':
                filtered_submissions = all_submissions.filter(status='submitted')
            elif status_filter == 'active':
                filtered_submissions = all_submissions.filter(status__in=['submitted', 'graded'])
            else:
                filtered_submissions = all_submissions
            # Organize submissions with additional info
            submissions_data = []
            for submission in filtered_submissions:
                try:
                    # Get student info
                    student = submission.student
                    assignment = submission.assignment
                    submissions_data.append({
                        'submission': submission,
                        'student': student,
                        'assignment': assignment,
                        'student_name': f"{student.first_name} {student.last_name}",
                        'student_id': student.student_id,
                        'assignment_title': assignment.title,
                        'submitted_date': submission.submitted_date,
                        'status': submission.status,
                        'is_late': submission.is_late,
                        'grade': getattr(submission, 'grade', None),
                        'feedback': getattr(submission, 'feedback', ''),
                    })
                except Exception as e:
                    print(f"DEBUG: Error processing submission: {e}")
                    continue
            # Get statistics
            total_submissions = len(submissions_data)
            pending_submissions = len([s for s in submissions_data if s['status'] == 'submitted'])
            graded_submissions = len([s for s in submissions_data if s['status'] == 'graded'])
            context.update({
                'subject': subject,
                'submissions_data': submissions_data,
                'total_assignments': assignments.count(),
                'total_submissions': total_submissions,
                'pending_submissions': pending_submissions,
                'graded_submissions': graded_submissions,
                'status_filter': status_filter,
                'filter_options': [
                    ('all', 'All Submissions'),
                    ('pending', 'Pending Review'),
                    ('active', 'Active Submissions'),
                ]
            })
        except BCASubject.DoesNotExist:
            messages.error(self.request, f'Subject {subject_code} not found!')
            context['subject'] = None
        except Exception as e:
            messages.error(self.request, f'Error loading submissions: {str(e)}')
            context['subject'] = None
        return context
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject_code = kwargs.get('subject_code')
        # Check if user is teacher or admin
        if self.request.user.role not in ['teacher', 'admin']:
            messages.error(self.request, 'Access denied! Only teachers and admins can view submissions.')
            return context
        try:
            # Get the subject
            subject = BCASubject.objects.get(subject_code=subject_code)
            # Check if teacher is assigned to this subject (unless admin)
            if self.request.user.role == 'teacher':
                teacher = Teacher.objects.filter(email=self.request.user.email).first()
                if not teacher or subject.assigned_teacher != teacher:
                    messages.error(self.request, 'You can only view submissions for subjects assigned to you.')
                    return context
            # Get filter status from URL parameters
            status_filter = self.request.GET.get('status', 'all')
            # Get all assignments for this subject
            assignments = Assignment.objects.filter(subject=subject).order_by('-created_date')
            # Get all submissions for these assignments
            all_submissions = AssignmentSubmission.objects.filter(
                assignment__in=assignments
            ).order_by('-submitted_date')
            # Filter submissions based on status
            if status_filter == 'pending':
                filtered_submissions = all_submissions.filter(status='submitted')
            elif status_filter == 'active':
                filtered_submissions = all_submissions.filter(status__in=['submitted', 'graded'])
            else:
                filtered_submissions = all_submissions
            # Organize submissions with additional info
            submissions_data = []
            for submission in filtered_submissions:
                try:
                    # Get student info
                    student = submission.student
                    assignment = submission.assignment
                    submissions_data.append({
                        'submission': submission,
                        'student': student,
                        'assignment': assignment,
                        'student_name': f"{student.first_name} {student.last_name}",
                        'student_id': student.student_id,
                        'assignment_title': assignment.title,
                        'submitted_date': submission.submitted_date,
                        'status': submission.status,
                        'is_late': submission.is_late,
                        'grade': getattr(submission, 'grade', None),
                        'feedback': getattr(submission, 'feedback', ''),
                    })
                except Exception as e:
                    print(f"DEBUG: Error processing submission: {e}")
                    continue
            # Get statistics
            total_submissions = len(submissions_data)
            pending_submissions = len([s for s in submissions_data if s['status'] == 'submitted'])
            graded_submissions = len([s for s in submissions_data if s['status'] == 'graded'])
            context.update({
                'subject': subject,
                'submissions_data': submissions_data,
                'total_assignments': assignments.count(),
                'total_submissions': total_submissions,
                'pending_submissions': pending_submissions,
                'graded_submissions': graded_submissions,
                'status_filter': status_filter,
                'filter_options': [
                    ('all', 'All Submissions'),
                    ('pending', 'Pending Review'),
                    ('active', 'Active Submissions'),
                ]
            })
        except BCASubject.DoesNotExist:
            messages.error(self.request, f'Subject {subject_code} not found!')
            context['subject'] = None
        except Exception as e:
            messages.error(self.request, f'Error loading submissions: {str(e)}')
            context['subject'] = None
        return context
class SubjectSubmissionsView(LoginRequiredMixin, TemplateView):
    """View submissions for all assignments in a specific subject"""
    template_name = "courses/assignment_submissions.html"
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject_code = kwargs.get("subject_code")
        # Check if user is teacher or admin
        if self.request.user.role not in ["teacher", "admin"]:
            messages.error(self.request, "Access denied! Only teachers and admins can view submissions.")
            return context
        try:
            # Get the subject
            subject = BCASubject.objects.get(subject_code=subject_code)
            # Check if teacher is assigned to this subject (unless admin)
            if self.request.user.role == "teacher":
                teacher = Teacher.objects.filter(email=self.request.user.email).first()
                if not teacher or subject.assigned_teacher != teacher:
                    messages.error(self.request, "You can only view submissions for subjects assigned to you.")
                    return context
            # Get filter status from URL parameters
            status_filter = self.request.GET.get("status", "all")
            # Get all assignments for this subject
            assignments = Assignment.objects.filter(subject=subject).order_by("-created_date")
            # Get all submissions for these assignments
            all_submissions = AssignmentSubmission.objects.filter(
                assignment__in=assignments
            ).order_by("-submitted_date")
            # Filter submissions based on status
            if status_filter == "pending":
                filtered_submissions = all_submissions.filter(status="submitted")
            elif status_filter == "active":
                filtered_submissions = all_submissions.filter(status__in=["submitted", "graded"])
            else:
                filtered_submissions = all_submissions
            # Organize submissions with additional info
            submissions_data = []
            for submission in filtered_submissions:
                try:
                    # Get student info
                    student = submission.student
                    assignment = submission.assignment
                    submissions_data.append({
                        "submission": submission,
                        "student": student,
                        "assignment": assignment,
                        "student_name": f"{student.first_name} {student.last_name}",
                        "student_id": student.student_id,
                        "assignment_title": assignment.title,
                        "submitted_date": submission.submitted_date,
                        "status": submission.status,
                        "is_late": submission.is_late,
                        "grade": getattr(submission, "grade", None),
                        "feedback": getattr(submission, "feedback", ""),
                    })
                except Exception as e:
                    print(f"DEBUG: Error processing submission: {e}")
                    continue
            # Get statistics
            total_submissions = len(submissions_data)
            pending_submissions = len([s for s in submissions_data if s["status"] == "submitted"])
            graded_submissions = len([s for s in submissions_data if s["status"] == "graded"])
            context.update({
                "subject": subject,
                "submissions_data": submissions_data,
                "total_assignments": assignments.count(),
                "total_submissions": total_submissions,
                "pending_submissions": pending_submissions,
                "graded_submissions": graded_submissions,
                "status_filter": status_filter,
                "filter_options": [
                    ("all", "All Submissions"),
                    ("pending", "Pending Review"),
                    ("active", "Active Submissions"),
                ]
            })
        except BCASubject.DoesNotExist:
            messages.error(self.request, f"Subject {subject_code} not found!")
            context["subject"] = None
        except Exception as e:
            messages.error(self.request, f"Error loading submissions: {str(e)}")
            context["subject"] = None
        return context
class SubjectSubmissionsView(LoginRequiredMixin, TemplateView):
    """View submissions for all assignments in a specific subject"""
    template_name = 'courses/assignment_submissions.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subject_code = kwargs.get('subject_code')
        # Check if user is teacher or admin
        if self.request.user.role not in ['teacher', 'admin']:
            messages.error(self.request, 'Access denied! Only teachers and admins can view submissions.')
            return context
        try:
            # Get the subject
            subject = BCASubject.objects.get(subject_code=subject_code)
            # Check if teacher is assigned to this subject (unless admin)
            if self.request.user.role == 'teacher':
                teacher = Teacher.objects.filter(email=self.request.user.email).first()
                if not teacher or subject.assigned_teacher != teacher:
                    messages.error(self.request, 'You can only view submissions for subjects assigned to you.')
                    return context
            # Get filter status from URL parameters
            status_filter = self.request.GET.get('status', 'all')
            # Get all assignments for this subject
            assignments = Assignment.objects.filter(subject=subject).order_by('-created_date')
            # Get all submissions for these assignments
            all_submissions = AssignmentSubmission.objects.filter(
                assignment__in=assignments
            ).order_by('-submitted_date')
            # Filter submissions based on status
            if status_filter == 'pending':
                filtered_submissions = all_submissions.filter(status='submitted')
            elif status_filter == 'active':
                # For "Active Assignment": show assignments that are currently active (not yet due)
                current_time = datetime.datetime.now()
                print(f"DEBUG: Current time: {current_time}")
                print(f"DEBUG: Total assignments before filter: {assignments.count()}")
                
                # Debug: Show all assignment due dates
                for assignment in assignments:
                    print(f"DEBUG: Assignment '{assignment.title}' due: {assignment.due_date}")
                
                active_assignments = assignments.filter(due_date__gt=current_time)
                print(f"DEBUG: Active assignments count: {active_assignments.count()}")
                
                filtered_submissions = AssignmentSubmission.objects.filter(
                    assignment__in=active_assignments
                ).order_by("-submitted_date")
                print(f"DEBUG: Submissions for active assignments: {filtered_submissions.count()}")
            else:
                filtered_submissions = all_submissions
            # Organize submissions with additional info
            submissions_data = []
            for submission in filtered_submissions:
                try:
                    # Get student info
                    student = submission.student
                    assignment = submission.assignment
                    submissions_data.append({
                        'submission': submission,
                        'student': student,
                        'assignment': assignment,
                        'student_name': f"{student.first_name} {student.last_name}",
                        'student_id': student.student_id,
                        'assignment_title': assignment.title,
                        'submitted_date': submission.submitted_date,
                        'status': submission.status,
                        'is_late': submission.is_late,
                        'grade': getattr(submission, 'grade', None),
                        'feedback': getattr(submission, 'feedback', ''),
                    })
                except Exception as e:
                    print(f"DEBUG: Error processing submission: {e}")
                    continue
            # Get statistics
            total_submissions = len(submissions_data)
            # Get statistics
            total_submissions = len(submissions_data)
            pending_submissions = len([s for s in submissions_data if s["status"] == "submitted"])
            graded_submissions = len([s for s in submissions_data if s["status"] == "graded"])
            
            # For active assignments, also pass the assignments themselves
            active_assignments_data = []
            if status_filter == "active":
                current_time = datetime.datetime.now()
                active_assignments = assignments.filter(due_date__gt=current_time)
                for assignment in active_assignments:
                    # Count submissions for this assignment
                    assignment_submissions = AssignmentSubmission.objects.filter(assignment=assignment)
                    active_assignments_data.append({
                        "assignment": assignment,
                        "title": assignment.title,
                        "description": assignment.description,
                        "due_date": assignment.due_date,
                        "created_date": assignment.created_date,
                        "total_submissions": assignment_submissions.count(),
                        "pending_submissions": assignment_submissions.filter(status="submitted").count(),
                        "graded_submissions": assignment_submissions.filter(status="graded").count(),
                    })
            
            context.update({
                "subject": subject,
                "submissions_data": submissions_data,
                "active_assignments_data": active_assignments_data,  # New: for Active Assignment view
                "total_assignments": assignments.count(),
                "total_submissions": total_submissions,
                "pending_submissions": pending_submissions,
                "graded_submissions": graded_submissions,
                "status_filter": status_filter,
                "is_active_assignments_view": status_filter == "active",  # New: flag for template
                "filter_options": [
                    ("all", "All Submissions"),
                    ("pending", "Pending Review"),
                    ("active", "Active Assignments"),
                ]
            })
        except BCASubject.DoesNotExist:
            messages.error(self.request, f'Subject {subject_code} not found!')
            context['subject'] = None
        except Exception as e:
            messages.error(self.request, f'Error loading submissions: {str(e)}')
            context['subject'] = None
        return context