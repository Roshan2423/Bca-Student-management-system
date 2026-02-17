# grades/views.py - Grade Management Views (IMPROVED VERSION)

from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from datetime import datetime
import json

from .models import ExamType, StudentGrade, GradeSummary
from students.models import Student
from courses.models import Teacher, BCASubject

# ============================================================================
# TEACHER/ADMIN ONLY MIXINS
# ============================================================================

class TeacherAdminRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure only teachers and admins can access certain views"""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role in ['admin', 'teacher']
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('accounts:login')
        
        # Redirect students to their grade view
        if self.request.user.role == 'student':
            messages.info(self.request, 'Students can only view their own grades.')
            return redirect('grades:student-grades')
        
        messages.error(self.request, 'Access denied! Only teachers and administrators can access this page.')
        return redirect('grades:dashboard')


class StudentOnlyMixin(UserPassesTestMixin):
    """Mixin to ensure only students can access certain views"""
    
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'student'
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('accounts:login')
        
        messages.error(self.request, 'Access denied! This page is for students only.')
        return redirect('grades:dashboard')


# ============================================================================
# TEACHER GRADE ASSIGNMENT VIEWS
# ============================================================================

class GradeDashboardView(LoginRequiredMixin, TemplateView):
    """Main grade management dashboard - accessible to all authenticated users"""
    template_name = 'grades/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Get exam types
            exam_types = ExamType.objects.filter(is_active=True)
            
            # Get basic statistics
            total_students = Student.objects.filter(is_active=True).count()
            total_subjects = BCASubject.objects.count()
            total_grades = StudentGrade.objects.count()
            
            # Get recent grade activities (limit based on user role)
            if self.request.user.role == 'student':
                # Students see only their own grades
                student = Student.objects.filter(email=self.request.user.email).first()
                if student:
                    recent_grades = StudentGrade.objects.filter(student=student).order_by('-assigned_date')[:5]
                else:
                    recent_grades = []
            else:
                # Teachers/admins see all recent grades
                recent_grades = StudentGrade.objects.order_by('-assigned_date')[:10]
            
            context.update({
                'exam_types': exam_types,
                'total_students': total_students,
                'total_subjects': total_subjects,
                'total_grades': total_grades,
                'recent_grades': recent_grades,
                'user_role': self.request.user.role,
            })
            
        except Exception as e:
            messages.error(self.request, f'Error loading grade dashboard: {str(e)}')
        
        return context


class AssignGradesView(TeacherAdminRequiredMixin, TemplateView):
    """Teacher interface to assign grades to students - TEACHERS/ADMIN ONLY"""
    template_name = 'grades/assign_grades.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        selected_semester = int(self.request.GET.get('semester', 1))
        selected_exam_type_id = self.request.GET.get('exam_type')
        selected_subject_id = self.request.GET.get('subject')
        
        try:
            # Get exam types
            exam_types = ExamType.objects.filter(is_active=True)
            
            # Get subjects based on user role
            if self.request.user.role == 'admin':
                # Admin can see all subjects for the semester
                subjects = BCASubject.objects.filter(semester=selected_semester)
            else:
                # Teachers can see all subjects (for now, until we determine the correct field)
                # TODO: Filter by teacher assignments once we know the correct field structure
                teacher = Teacher.objects.filter(email=self.request.user.email).first()
                if teacher:
                    # For now, show all subjects for the semester
                    # Later we can filter based on the actual teacher-subject relationship
                    subjects = BCASubject.objects.filter(semester=selected_semester)
                    
                    # Add a message indicating this is temporary
                    messages.info(
                        self.request, 
                        f'Showing all subjects for Semester {selected_semester}. Subject filtering will be implemented once teacher assignments are configured.'
                    )
                else:
                    subjects = BCASubject.objects.none()
                    messages.warning(self.request, 'Teacher profile not found. Contact administrator.')
            
            # Get selected exam type and subject
            selected_exam_type = None
            selected_subject = None
            students_with_grades = []
            
            if selected_exam_type_id:
                try:
                    selected_exam_type = ExamType.objects.get(id=selected_exam_type_id)
                except ExamType.DoesNotExist:
                    messages.error(self.request, 'Selected exam type not found.')
            
            if selected_subject_id:
                try:
                    selected_subject = BCASubject.objects.get(id=selected_subject_id)
                    
                    # Get students in this semester
                    students = Student.objects.filter(
                        current_semester=selected_semester,
                        is_active=True
                    ).order_by('first_name', 'last_name')
                    
                    # Get existing grades for these students
                    existing_grades = {}
                    if selected_exam_type:
                        grades = StudentGrade.objects.filter(
                            subject=selected_subject,
                            exam_type=selected_exam_type
                        )
                        existing_grades = {grade.student.id: grade for grade in grades}
                    
                    # Prepare student data with current grades
                    for student in students:
                        existing_grade = existing_grades.get(student.id)
                        students_with_grades.append({
                            'student': student,
                            'current_grade': existing_grade,
                            'has_grade': existing_grade is not None
                        })
                        
                except BCASubject.DoesNotExist:
                    messages.error(self.request, 'Selected subject not found.')
            
            context.update({
                'exam_types': exam_types,
                'subjects': subjects,
                'selected_semester': selected_semester,
                'selected_exam_type': selected_exam_type,
                'selected_subject': selected_subject,
                'students_with_grades': students_with_grades,
                'semester_choices': Student.SEMESTER_CHOICES,
                'is_admin': self.request.user.role == 'admin',
            })
            
        except Exception as e:
            messages.error(self.request, f'Error loading grade assignment: {str(e)}')
            # Log the actual error for debugging
            print(f"DEBUG: Grade assignment error: {str(e)}")
        
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            # Get form data
            exam_type_id = request.POST.get('exam_type')
            subject_id = request.POST.get('subject')
            
            exam_type = ExamType.objects.get(id=exam_type_id)
            subject = BCASubject.objects.get(id=subject_id)
            
            # Get teacher who is assigning grades
            teacher = None
            if request.user.role == 'teacher':
                teacher = Teacher.objects.filter(email=request.user.email).first()
            else:
                # For admin, we'll need a default teacher or handle differently
                teacher = Teacher.objects.first()  # Temporary solution
            
            grades_assigned = 0
            grades_updated = 0
            
            # Process each student's grade
            for key, value in request.POST.items():
                if key.startswith('marks_'):
                    student_id = key.replace('marks_', '')
                    
                    if value and value.strip():  # Only process if marks are provided
                        try:
                            marks = int(value.strip())
                            
                            # Validate marks
                            if marks < 0 or marks > exam_type.total_marks:
                                messages.warning(
                                    request,
                                    f'Invalid marks for student {student_id}: {marks}. Must be between 0 and {exam_type.total_marks}.'
                                )
                                continue
                            
                            # Get student
                            student = Student.objects.get(id=student_id)
                            
                            # Get remarks if any
                            remarks = request.POST.get(f'remarks_{student_id}', '')
                            
                            # Assign or update grade
                            grade = StudentGrade.assign_grade(
                                student=student,
                                subject=subject,
                                exam_type=exam_type,
                                marks_obtained=marks,
                                assigned_by=teacher,
                                remarks=remarks
                            )
                            
                            if grade:
                                grades_assigned += 1
                            
                        except (ValueError, Student.DoesNotExist) as e:
                            messages.warning(request, f'Error processing grade for student {student_id}: {str(e)}')
                            continue
            
            if grades_assigned > 0:
                messages.success(
                    request,
                    f'Successfully assigned {grades_assigned} grades for {subject.subject_name} - {exam_type.exam_name}'
                )
                
                # Update grade summaries for affected students
                semester = int(request.POST.get('semester', 1))
                students = Student.objects.filter(current_semester=semester, is_active=True)
                for student in students:
                    GradeSummary.calculate_summary(student, exam_type)
            else:
                messages.warning(request, 'No grades were assigned. Please check your input.')
            
            return redirect(request.get_full_path())
            
        except Exception as e:
            messages.error(request, f'Error assigning grades: {str(e)}')
            return self.get(request, *args, **kwargs)


# ============================================================================
# STUDENT GRADE VIEWING
# ============================================================================

class StudentGradeView(StudentOnlyMixin, TemplateView):
    """Student view of their own grades - STUDENTS ONLY"""
    template_name = 'grades/student_grades.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            # Get student profile
            student = Student.objects.filter(email=self.request.user.email).first()
            if not student:
                messages.warning(self.request, 'Student profile not found.')
                context['student'] = None
                return context
            
            # Get exam types
            exam_types = ExamType.objects.filter(is_active=True)
            
            # Get subjects for student's current semester
            subjects = BCASubject.objects.filter(semester=student.current_semester)
            
            # Get ALL grades for this student
            all_grades = StudentGrade.objects.filter(student=student)
            
            print(f"DEBUG: Found {all_grades.count()} grades for student {student.first_name}")
            
            # Create a simple list of all student grades for easy template access
            student_grades = []
            for grade in all_grades:
                student_grades.append({
                    'subject': grade.subject,
                    'subject_name': grade.subject.subject_name,
                    'subject_code': grade.subject.subject_code,
                    'exam_type': grade.exam_type,
                    'exam_name': grade.exam_type.exam_name,
                    'marks_obtained': grade.marks_obtained,
                    'total_marks': grade.exam_type.total_marks,
                    'percentage': grade.percentage,
                    'is_pass': grade.is_pass,
                    'remarks': grade.remarks,
                    'assigned_date': grade.assigned_date,
                })
                print(f"DEBUG: Added grade - {grade.subject.subject_name}: {grade.marks_obtained}/{grade.exam_type.total_marks}")
            
            # Organize grades by exam type and subject (for detailed view)
            grades_by_exam = {}
            total_grades = 0
            passed_grades = 0
            
            for exam_type in exam_types:
                exam_grades = all_grades.filter(exam_type=exam_type)
                print(f"DEBUG: {exam_type.exam_name}: {exam_grades.count()} grades")
                
                # Create grades dictionary by subject for this exam
                grades_by_subject = {}
                exam_passed = 0
                exam_total_marks = 0
                exam_obtained_marks = 0
                
                for grade in exam_grades:
                    grades_by_subject[str(grade.subject.id)] = {
                        'id': grade.id,
                        'subject': grade.subject,
                        'marks_obtained': grade.marks_obtained,
                        'total_marks': exam_type.total_marks,
                        'percentage': grade.percentage,
                        'is_pass': grade.is_pass,
                        'remarks': grade.remarks,
                        'assigned_date': grade.assigned_date,
                    }
                    total_grades += 1
                    if grade.is_pass:
                        passed_grades += 1
                        exam_passed += 1
                    exam_obtained_marks += grade.marks_obtained
                    exam_total_marks += exam_type.total_marks
                    
                    print(f"DEBUG: Grade organized - Subject: {grade.subject.subject_name}, Marks: {grade.marks_obtained}")
                
                # Calculate summary for this exam
                summary = None
                if exam_grades.count() > 0:
                    summary = {
                        'total_subjects': subjects.count(),
                        'subjects_passed': exam_passed,
                        'subjects_failed': exam_grades.count() - exam_passed,
                        'total_marks_obtained': exam_obtained_marks,
                        'total_marks_possible': exam_total_marks,
                        'overall_percentage': round((exam_obtained_marks / exam_total_marks * 100), 1) if exam_total_marks > 0 else 0,
                        'overall_result': 'Pass' if exam_passed >= exam_grades.count() / 2 else 'Fail'
                    }
                
                grades_by_exam[str(exam_type.id)] = {
                    'exam_type': exam_type,
                    'grades': grades_by_subject,
                    'summary': summary,
                    'total_subjects': subjects.count(),
                    'graded_subjects': exam_grades.count()
                }
            
            # Calculate overall performance
            failed_grades = total_grades - passed_grades
            overall_pass_rate = round((passed_grades / total_grades * 100), 1) if total_grades > 0 else 0
            
            print(f"DEBUG: Total grades: {total_grades}, Passed: {passed_grades}, Pass rate: {overall_pass_rate}%")
            print(f"DEBUG: Student grades list has {len(student_grades)} items")
            
            context.update({
                'student': student,
                'exam_types': exam_types,
                'subjects': subjects,
                'grades_by_exam': grades_by_exam,
                'student_grades': student_grades,  # Simple list for easy template access
                'total_grades': total_grades,
                'passed_grades': passed_grades,
                'failed_grades': failed_grades,
                'overall_pass_rate': overall_pass_rate,
            })
            
        except Exception as e:
            messages.error(self.request, f'Error loading student grades: {str(e)}')
            print(f"DEBUG: Error in StudentGradeView: {str(e)}")
            import traceback
            traceback.print_exc()
            context['student'] = None
        
        return context


# ============================================================================
# GRADE REPORTS
# ============================================================================

class GradeReportsView(TeacherAdminRequiredMixin, TemplateView):
    """Comprehensive grade reports with subject filtering - TEACHERS/ADMIN ONLY"""
    template_name = 'grades/reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        selected_semester = int(self.request.GET.get('semester', 1))
        selected_exam_type_id = self.request.GET.get('exam_type')
        selected_subject_id = self.request.GET.get('subject')  # NEW: Subject filtering
        
        try:
            exam_types = ExamType.objects.filter(is_active=True)
            selected_exam_type = None
            selected_subject = None
            
            if selected_exam_type_id:
                selected_exam_type = ExamType.objects.get(id=selected_exam_type_id)
            
            if selected_subject_id:
                selected_subject = BCASubject.objects.get(id=selected_subject_id)
            
            # Get subjects for the selected semester
            subjects = BCASubject.objects.filter(semester=selected_semester)
            
            # Get semester statistics
            semester_students = Student.objects.filter(
                current_semester=selected_semester,
                is_active=True
            )
            
            semester_stats = {
                'total_students': semester_students.count(),
                'subjects_count': subjects.count()
            }
            
            # Initialize variables
            exam_stats = {}
            grade_details = []
            subject_summaries = []
            
            if selected_exam_type:
                if selected_subject:
                    # Show detailed grades for specific subject
                    grades = StudentGrade.objects.filter(
                        exam_type=selected_exam_type,
                        subject=selected_subject,
                        semester=selected_semester
                    ).order_by('student__first_name', 'student__last_name')
                    
                    grade_details = list(grades)
                    
                    # Calculate exam stats for this subject
                    total_graded = grades.count()
                    passed_count = grades.filter(is_pass=True).count()
                    failed_count = total_graded - passed_count
                    
                    if total_graded > 0:
                        avg_percentage = sum(grade.percentage for grade in grades) / total_graded
                    else:
                        avg_percentage = 0
                    
                    exam_stats = {
                        'students_graded': total_graded,
                        'students_passed': passed_count,
                        'students_failed': failed_count,
                        'average_percentage': round(avg_percentage, 1)
                    }
                    
                else:
                    # Show subject-wise summary for all subjects in semester
                    subject_summaries = []
                    total_graded_all = 0
                    total_passed_all = 0
                    total_failed_all = 0
                    all_percentages = []
                    
                    for subject in subjects:
                        subject_grades = StudentGrade.objects.filter(
                            exam_type=selected_exam_type,
                            subject=subject,
                            semester=selected_semester
                        )
                        
                        graded_count = subject_grades.count()
                        passed_count = subject_grades.filter(is_pass=True).count()
                        failed_count = graded_count - passed_count
                        
                        if graded_count > 0:
                            pass_rate = round((passed_count / graded_count) * 100, 1)
                            avg_marks = sum(grade.marks_obtained for grade in subject_grades) / graded_count
                            total_marks = subject_grades.first().total_marks if subject_grades.first() else 60
                            
                            # Add to overall stats
                            total_graded_all += graded_count
                            total_passed_all += passed_count
                            total_failed_all += failed_count
                            all_percentages.extend([grade.percentage for grade in subject_grades])
                        else:
                            pass_rate = 0
                            avg_marks = 0
                            total_marks = 60
                        
                        subject_summaries.append({
                            'subject': subject,
                            'total_students': semester_students.count(),
                            'graded_students': graded_count,
                            'passed_students': passed_count,
                            'failed_students': failed_count,
                            'pass_rate': pass_rate,
                            'average_marks': round(avg_marks, 1),
                            'total_marks': total_marks
                        })
                    
                    # Overall exam stats across all subjects
                    if all_percentages:
                        overall_avg = sum(all_percentages) / len(all_percentages)
                    else:
                        overall_avg = 0
                    
                    exam_stats = {
                        'students_graded': total_graded_all,
                        'students_passed': total_passed_all,
                        'students_failed': total_failed_all,
                        'average_percentage': round(overall_avg, 1)
                    }
            
            context.update({
                'exam_types': exam_types,
                'subjects': subjects,
                'selected_semester': selected_semester,
                'selected_exam_type': selected_exam_type,
                'selected_subject': selected_subject,
                'semester_choices': Student.SEMESTER_CHOICES,
                'semester_stats': semester_stats,
                'exam_stats': exam_stats,
                'grade_details': grade_details,  # NEW: Individual grades
                'subject_summaries': subject_summaries,  # NEW: Subject summaries
            })
            
        except Exception as e:
            messages.error(self.request, f'Error generating reports: {str(e)}')
            print(f"DEBUG: Error in GradeReportsView: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return context