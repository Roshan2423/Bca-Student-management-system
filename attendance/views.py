# attendance/views.py - Clean Teacher Self-Attendance System

from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.contrib import messages
from django.http import JsonResponse
from datetime import datetime, timedelta
import json

from .models import DailyAttendance
from courses.models import Teacher
from students.models import Student

# ============================================================================
# MAIN DASHBOARD
# ============================================================================

class AttendanceDashboardView(LoginRequiredMixin, TemplateView):
    """Main attendance dashboard for admins and teachers"""
    template_name = 'attendance/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.role not in ['admin', 'teacher']:
            messages.error(self.request, 'Access denied!')
            return context
        
        try:
            # Get today's date
            today = datetime.now().date()
            
            # Get all students and teachers
            all_students = Student.objects.all()
            all_teachers = Teacher.objects.all()
            
            # Get today's attendance records
            today_student_attendance = {}
            today_teacher_attendance = {}
            
            for record in DailyAttendance.objects.filter(date=today):
                if record.student:
                    today_student_attendance[record.student.student_id] = record.is_present
                elif record.teacher:
                    today_teacher_attendance[record.teacher.teacher_id] = record.is_present
            
            # Calculate statistics
            total_students = all_students.count()
            total_teachers = all_teachers.count()
            
            students_present_today = sum(1 for present in today_student_attendance.values() if present)
            students_marked_today = len(today_student_attendance)
            students_not_marked = total_students - students_marked_today
            
            teachers_present_today = sum(1 for present in today_teacher_attendance.values() if present)
            teachers_marked_today = len(today_teacher_attendance)
            teachers_not_marked = total_teachers - teachers_marked_today
            
            context.update({
                'today_date': today,
                'total_students': total_students,
                'total_teachers': total_teachers,
                'students_present_today': students_present_today,
                'students_absent_today': students_marked_today - students_present_today,
                'students_not_marked': students_not_marked,
                'student_attendance_percentage': round((students_present_today / students_marked_today * 100), 1) if students_marked_today > 0 else 0,
                'today_student_attendance': today_student_attendance,
                'teachers_present_today': teachers_present_today,
                'teachers_absent_today': teachers_marked_today - teachers_present_today,
                'teachers_not_marked': teachers_not_marked,
                'teacher_attendance_percentage': round((teachers_present_today / teachers_marked_today * 100), 1) if teachers_marked_today > 0 else 0,
            })
            
        except Exception as e:
            messages.error(self.request, f'Error loading dashboard: {str(e)}')
            
        return context

# ============================================================================
# TEACHER SELF-ATTENDANCE SYSTEM
# ============================================================================

class TeacherSelfAttendanceView(LoginRequiredMixin, TemplateView):
    """Teachers mark their own attendance"""
    template_name = 'attendance/mark_teacher_attendance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.role != 'teacher':
            messages.error(self.request, 'Access denied! Only teachers can mark their own attendance.')
            return context
        
        try:
            # Get current teacher
            teacher = Teacher.objects.get(email=self.request.user.email)
            
            # Get date from request (default to today)
            selected_date_str = self.request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            
            # Get teacher's existing attendance for this date
            existing_attendance = DailyAttendance.objects.filter(
                teacher=teacher,
                date=selected_date
            ).first()
            
            context.update({
                'is_teacher_self_marking': True,
                'current_teacher': teacher,
                'selected_date': selected_date,
                'selected_date_str': selected_date_str,
                'existing_attendance': existing_attendance,
                'can_modify': existing_attendance is None or existing_attendance.status in ['pending', 'rejected']
            })
            
        except Teacher.DoesNotExist:
            messages.error(self.request, 'Teacher profile not found!')
            context['current_teacher'] = None
        except Exception as e:
            messages.error(self.request, f'Error loading attendance: {str(e)}')
            context['current_teacher'] = None
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle teacher self-attendance submission"""
        if request.user.role != 'teacher':
            messages.error(request, 'Access denied!')
            return redirect('attendance:dashboard')
        
        try:
            teacher = Teacher.objects.get(email=request.user.email)
            attendance_date_str = request.POST.get('attendance_date')
            attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
            is_present = request.POST.get('is_present') == 'true'
            notes = request.POST.get('notes', '')
            
            # Check if future date
            if attendance_date > datetime.now().date():
                messages.error(request, 'Cannot mark attendance for future dates!')
                return redirect('attendance:teacher-self-mark')
            
            # Mark self-attendance
            attendance = DailyAttendance.teacher_self_mark_attendance(
                teacher=teacher,
                date=attendance_date,
                is_present=is_present,
                notes=notes
            )
            
            status_msg = "Present" if is_present else "Absent"
            messages.success(request, f'Attendance marked as {status_msg} for {attendance_date}. Waiting for admin approval.')
            return redirect('attendance:teacher-self-mark')
            
        except Teacher.DoesNotExist:
            messages.error(request, 'Teacher profile not found!')
        except Exception as e:
            messages.error(request, f'Error marking attendance: {str(e)}')
        
        return redirect('attendance:teacher-self-mark')


class MarkTeacherAttendanceView(LoginRequiredMixin, TemplateView):
    """Admin reviews and approves/rejects teacher attendance submissions"""
    template_name = 'attendance/mark_teacher_attendance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.role not in ['admin']:
            messages.error(self.request, 'Access denied! Only admin can manage teacher attendance.')
            return context
        
        try:
            # Get filter parameters
            status_filter = self.request.GET.get('status', 'pending')
            date_filter = self.request.GET.get('date', '')
            
            # Build query for attendance records
            query = {'person_type': 'teacher', 'self_marked': True}
            
            # Apply date filter
            if date_filter:
                selected_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
                query['date'] = selected_date
            else:
                # Default to last 7 days
                week_ago = datetime.now().date() - timedelta(days=7)
                query['date__gte'] = week_ago
                selected_date = None
            
            # Apply status filter
            if status_filter != 'all':
                query['status'] = status_filter
            
            # Get attendance records
            attendance_records = DailyAttendance.objects.filter(**query).order_by('-date', 'teacher__first_name')
            
            # Group records by teacher
            teacher_attendance_data = {}
            for record in attendance_records:
                if record.teacher:
                    teacher_id = record.teacher.teacher_id
                    if teacher_id not in teacher_attendance_data:
                        teacher_attendance_data[teacher_id] = {
                            'teacher': record.teacher,
                            'records': []
                        }
                    teacher_attendance_data[teacher_id]['records'].append(record)
            
            # Get pending counts for dashboard
            pending_count = DailyAttendance.objects.filter(
                person_type='teacher', 
                self_marked=True, 
                status='pending'
            ).count()
            
            context.update({
                'is_admin_approval_view': True,
                'teacher_attendance_data': teacher_attendance_data,
                'status_filter': status_filter,
                'date_filter': date_filter,
                'selected_date': selected_date,
                'pending_count': pending_count,
                'total_records': len(attendance_records)
            })
            
        except Exception as e:
            messages.error(self.request, f'Error loading teacher attendance: {str(e)}')
        
        return context


@login_required
def approve_teacher_attendance(request):
    """Admin approves or rejects teacher attendance"""
    if request.method == 'POST' and request.user.role == 'admin':
        try:
            attendance_id = request.POST.get('attendance_id')
            action = request.POST.get('action')  # 'approve' or 'reject'
            admin_notes = request.POST.get('admin_notes', '')
            
            attendance = DailyAttendance.objects.get(id=attendance_id)
            
            if not attendance.teacher or not attendance.self_marked:
                return JsonResponse({'success': False, 'error': 'Invalid attendance record'})
            
            # Get admin teacher profile
            admin_teacher = Teacher.objects.filter(email=request.user.email).first()
            
            if action == 'approve':
                attendance.approve_attendance(admin_teacher, admin_notes)
                message = f"Approved attendance for {attendance.teacher.full_name} on {attendance.date}"
            elif action == 'reject':
                attendance.reject_attendance(admin_teacher, admin_notes)
                message = f"Rejected attendance for {attendance.teacher.full_name} on {attendance.date}"
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})
            
            return JsonResponse({
                'success': True,
                'message': message,
                'new_status': attendance.status,
                'status_display': attendance.get_status_display()
            })
            
        except DailyAttendance.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Attendance record not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request'})

# ============================================================================
# STUDENT ATTENDANCE VIEWS
# ============================================================================

class MarkStudentAttendanceView(LoginRequiredMixin, TemplateView):
    """Mark attendance for students by semester/subject"""
    template_name = 'attendance/mark_student_attendance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.role not in ['admin', 'teacher']:
            messages.error(self.request, 'Access denied!')
            return context
        
        # Get selected semester (default: 1st semester)
        selected_semester = int(self.request.GET.get('semester', 1))
        selected_date = self.request.GET.get('date', datetime.now().date().strftime('%Y-%m-%d'))
        
        try:
            # Get students from selected semester
            students_in_semester = Student.objects.filter(
                current_semester=selected_semester,
                is_active=True
            ).order_by('student_id')
            
            # Get existing attendance for the selected date
            existing_attendance = {}
            attendance_records = DailyAttendance.objects.filter(
                date=datetime.strptime(selected_date, '%Y-%m-%d').date(),
                person_type='student'
            )
            
            for record in attendance_records:
                if record.student:
                    existing_attendance[record.student.student_id] = record.is_present
            
            # Prepare student list with attendance status
            student_data = []
            for student in students_in_semester:
                student_info = {
                    'student': student,
                    'current_status': existing_attendance.get(student.student_id, None),
                    'is_marked': student.student_id in existing_attendance
                }
                student_data.append(student_info)
            
            # Semester choices for dropdown - provide as list of numbers
            all_semesters = list(range(1, 9))
            
            context.update({
                'selected_semester': selected_semester,
                'selected_date': selected_date,
                'student_list': student_data,  # Template expects 'student_list'
                'all_semesters': all_semesters,  # Template expects 'all_semesters'
                'total_students': len(student_data),
                'marked_students': len(existing_attendance),
                'present_students': sum(1 for present in existing_attendance.values() if present),
                'absent_students': sum(1 for present in existing_attendance.values() if not present)
            })
            
        except Exception as e:
            messages.error(self.request, f'Error loading student attendance: {str(e)}')
        
        return context
    
    def post(self, request, *args, **kwargs):
        if request.user.role not in ['admin', 'teacher']:
            messages.error(request, 'Access denied!')
            return redirect('attendance:dashboard')
        
        try:
            attendance_date = datetime.strptime(request.POST.get('attendance_date'), '%Y-%m-%d').date()
            selected_semester = int(request.POST.get('semester', 1))
            
            present_count = 0
            absent_count = 0
            
            # Get marker (teacher if role is teacher)
            marker = Teacher.objects.filter(email=request.user.email).first() if request.user.role == 'teacher' else None
            
            # Process attendance data
            for key, value in request.POST.items():
                if key.startswith('attendance_'):
                    student_id = key.replace('attendance_', '')
                    is_present = value == 'present'
                    
                    try:
                        student = Student.objects.get(student_id=student_id)
                        
                        # Mark attendance for this student
                        DailyAttendance.mark_student_attendance(
                            student=student,
                            date=attendance_date,
                            is_present=is_present,
                            marked_by=marker
                        )
                        
                        if is_present:
                            present_count += 1
                        else:
                            absent_count += 1
                            
                    except Student.DoesNotExist:
                        continue
            
            messages.success(request, f'Student attendance marked successfully! Present: {present_count}, Absent: {absent_count}')
            return redirect(f'{request.path}?semester={selected_semester}&date={attendance_date.strftime("%Y-%m-%d")}')
            
        except Exception as e:
            messages.error(request, f'Error marking student attendance: {str(e)}')
            return self.get(request, *args, **kwargs)


class StudentAttendanceView(LoginRequiredMixin, TemplateView):
    """Student view - see their own attendance records"""
    template_name = 'attendance/student_attendance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.role != 'student':
            messages.error(self.request, 'Access denied! Only students can view this page.')
            return context
        
        try:
            # Get current student
            student = Student.objects.get(email=self.request.user.email)
            
            # Get attendance records for the last 30 days
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            
            attendance_records = DailyAttendance.objects.filter(
                student=student,
                date__gte=start_date,
                date__lte=end_date
            ).order_by('-date')
            
            # Calculate statistics
            stats = DailyAttendance.get_student_attendance_stats(student, days=30)
            
            context.update({
                'student': student,
                'attendance_records': attendance_records,
                'stats': stats,
                'start_date': start_date,
                'end_date': end_date
            })
            
        except Student.DoesNotExist:
            messages.error(self.request, 'Student profile not found!')
            context['student'] = None
        except Exception as e:
            messages.error(self.request, f'Error loading attendance: {str(e)}')
            context['student'] = None
        
        return context

# ============================================================================
# REPORTS AND AJAX
# ============================================================================

class AttendanceReportsView(LoginRequiredMixin, TemplateView):
    """Generate attendance reports"""
    template_name = 'attendance/reports.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.user.role not in ['admin', 'teacher']:
            messages.error(self.request, 'Access denied!')
            return context
        
        # Get filter parameters
        person_type = self.request.GET.get('type', 'student')
        date_from_str = self.request.GET.get('date_from', '')
        date_to_str = self.request.GET.get('date_to', '')
        
        # Set default date range (last 30 days)
        if not date_from_str or not date_to_str:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(date_from_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        
        try:
            # Get attendance records in date range
            attendance_records = DailyAttendance.objects.filter(
                date__gte=start_date,
                date__lte=end_date,
                person_type=person_type
            )
            
            # Calculate summary statistics
            total_records = attendance_records.count()
            present_records = attendance_records.filter(is_present=True).count()
            absent_records = total_records - present_records
            overall_percentage = round((present_records / total_records * 100), 1) if total_records > 0 else 0
            
            # Generate individual statistics
            person_list = []
            
            if person_type == 'student':
                # Get all students who have attendance records in this period
                student_ids = set(r.student.id for r in attendance_records if r.student)
                for student_id in student_ids:
                    student = Student.objects.get(id=student_id)
                    student_records = attendance_records.filter(student=student)
                    
                    present_days = student_records.filter(is_present=True).count()
                    total_days = student_records.count()
                    absent_days = total_days - present_days
                    percentage = round((present_days / total_days * 100), 1) if total_days > 0 else 0
                    
                    person_list.append({
                        'name': student.full_name,
                        'id': student.student_id,
                        'present': present_days,
                        'absent': absent_days,
                        'total': total_days,
                        'percentage': percentage
                    })
            
            elif person_type == 'teacher':
                # Get all teachers who have attendance records in this period
                teacher_ids = set(r.teacher.id for r in attendance_records if r.teacher)
                for teacher_id in teacher_ids:
                    teacher = Teacher.objects.get(id=teacher_id)
                    teacher_records = attendance_records.filter(teacher=teacher)
                    
                    present_days = teacher_records.filter(is_present=True).count()
                    total_days = teacher_records.count()
                    absent_days = total_days - present_days
                    percentage = round((present_days / total_days * 100), 1) if total_days > 0 else 0
                    
                    person_list.append({
                        'name': teacher.full_name,
                        'id': teacher.teacher_id,
                        'present': present_days,
                        'absent': absent_days,
                        'total': total_days,
                        'percentage': percentage
                    })
            
            # Sort by percentage (highest first)
            person_list.sort(key=lambda x: x['percentage'], reverse=True)
            
            context.update({
                'person_type': person_type,
                'date_from': start_date.strftime('%Y-%m-%d'),
                'date_to': end_date.strftime('%Y-%m-%d'),
                'total_records': total_records,
                'present_records': present_records,
                'absent_records': absent_records,
                'overall_percentage': overall_percentage,
                'person_list': person_list,
                'date_range_display': f"{start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}"
            })
                
        except Exception as e:
            messages.error(self.request, f'Error generating report: {str(e)}')
            context.update({
                'person_type': person_type,
                'date_from': start_date.strftime('%Y-%m-%d') if 'start_date' in locals() else '',
                'date_to': end_date.strftime('%Y-%m-%d') if 'end_date' in locals() else '',
                'total_records': 0,
                'present_records': 0,
                'absent_records': 0,
                'overall_percentage': 0,
                'person_list': []
            })
        
        return context


@login_required
def quick_mark_attendance(request):
    """AJAX endpoint for quick attendance marking"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            person_type = data.get('person_type')  # 'student' or 'teacher'
            person_id = data.get('person_id')
            is_present = data.get('is_present', False)
            attendance_date = datetime.strptime(data.get('date'), '%Y-%m-%d').date()
            
            if person_type == 'student' and request.user.role in ['admin', 'teacher']:
                student = Student.objects.get(student_id=person_id)
                marker = Teacher.objects.filter(email=request.user.email).first() if request.user.role == 'teacher' else None
                
                DailyAttendance.mark_student_attendance(
                    student=student,
                    date=attendance_date,
                    is_present=is_present,
                    marked_by=marker
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Student attendance marked: {"Present" if is_present else "Absent"}'
                })
                
            elif person_type == 'teacher' and request.user.role == 'admin':
                teacher = Teacher.objects.get(teacher_id=person_id)
                
                DailyAttendance.mark_teacher_attendance(
                    teacher=teacher,
                    date=attendance_date,
                    is_present=is_present
                )
                
                return JsonResponse({
                    'success': True,
                    'message': f'Teacher attendance marked: {"Present" if is_present else "Absent"}'
                })
            
            return JsonResponse({'success': False, 'error': 'Invalid request'})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})