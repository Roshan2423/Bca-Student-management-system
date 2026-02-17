# dashboard/views.py - IMPROVED VERSION

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required
def dashboard_redirect(request):
    """Route users to appropriate dashboard based on their role"""
    
    user = request.user
    user_role = getattr(user, 'role', None)
    
    # Debug: User role check (commented out to avoid Windows console issues)
    # print(f"DEBUG: User {user.email} has role: {user_role}")
    
    # Check if user is admin (superuser, staff, or role='admin')
    if user.is_superuser or user.is_staff or user_role == 'admin':
        return redirect('admin_dashboard')
    
    # Check if user is teacher
    elif user_role == 'teacher':
        # Check if teacher profile exists in MongoDB
        try:
            from courses.models import Teacher
            teacher = Teacher.objects.filter(email=user.email).first()
            if teacher:
                return redirect('courses:teacher-dashboard')
            else:
                messages.warning(request, 'Teacher profile not found. Please contact administrator.')
                return redirect('admin_dashboard')  # Fallback to admin dashboard
        except Exception as e:
            # DEBUG: Error checking teacher (commented out to avoid console issues)
            # print(f"DEBUG: Error checking teacher: {e}")
            messages.error(request, 'Error accessing teacher dashboard.')
            return redirect('admin_dashboard')
    
    # Check if user is student
    elif user_role == 'student':
        # Check if student profile exists in MongoDB
        try:
            from students.models import Student
            student = Student.objects.filter(email=user.email).first()
            if student:
                return redirect('courses:student-dashboard')
            else:
                messages.warning(request, 'Student profile not found. Please contact administrator.')
                return redirect('admin_dashboard')  # Fallback to admin dashboard
        except Exception as e:
            # DEBUG: Error checking student (commented out to avoid console issues)
            # print(f"DEBUG: Error checking student: {e}")
            messages.error(request, 'Error accessing student dashboard.')
            return redirect('admin_dashboard')
    
    else:
        # Unknown role or no role set
        messages.error(request, f'Unknown user role: {user_role}. Please contact administrator.')
        return redirect('admin_dashboard')  # Always have a fallback

@login_required 
def admin_dashboard(request):
    """Admin-only dashboard with management functions"""
    
    # Import here to avoid circular imports
    from students.models import Student
    from courses.models import Teacher, BCASubject
    
    try:
        # Get statistics for admin dashboard
        total_students = Student.objects.count()
        active_students = Student.objects.filter(is_active=True).count()
        total_teachers = Teacher.objects.count()
        total_subjects = BCASubject.objects.count()
        
        context = {
            'total_students': total_students,
            'active_students': active_students, 
            'total_teachers': total_teachers,
            'total_subjects': total_subjects,
            'user': request.user,
        }
        
    except Exception as e:
        # If there's an error getting stats, use defaults
        # DEBUG: Error getting stats (commented out to avoid console issues)
        # print(f"DEBUG: Error getting stats: {e}")
        context = {
            'total_students': 0,
            'active_students': 0,
            'total_teachers': 0, 
            'total_subjects': 0,
            'user': request.user,
        }
    
    return render(request, 'dashboard/main.html', context)