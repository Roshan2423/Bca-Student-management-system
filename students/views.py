from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.contrib.auth import get_user_model
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from mongoengine import DoesNotExist
from mongoengine import Q
from .models import Student, StudentDocument
from .serializers import StudentSerializer, StudentDocumentSerializer
from .utils import sort_students_by_name, sort_students_by_roll
from .algorithms import binary_search_students
from .random_forest_analysis import run_random_forest_analysis
from .kmeans_clustering import run_kmeans_clustering
import datetime
import string
import secrets
from django.http import JsonResponse


User = get_user_model()


class StudentListView(LoginRequiredMixin, TemplateView):
    """Display list of students with search and filter functionality using custom algorithms"""
    template_name = 'students/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all students from MongoDB
        students = Student.objects.all()
        
        # Apply semester filter
        semester = self.request.GET.get('semester', '')
        if semester:
            students = students.filter(current_semester=int(semester))
        
        # Apply program filter
        program = self.request.GET.get('program', '')
        if program:
            students = students.filter(program=program)
        
        # Apply status filter
        status_filter = self.request.GET.get('status', '')
        if status_filter == 'active':
            students = students.filter(is_active=True)
        elif status_filter == 'inactive':
            students = students.filter(is_active=False)
        
        # Convert queryset to list for custom algorithm usage
        students_list = list(students)
        
        # Apply custom binary search algorithm for faster search
        search = self.request.GET.get('search', '')
        if search:
            students_list = binary_search_students(students_list, search)
        
        # Sorting (using your custom sort algorithm)
        sort_type = self.request.GET.get('sort', 'name')  # Default sort by name
        if sort_type == 'roll':
            students_sorted = sort_students_by_roll(students_list)
        else:
            students_sorted = sort_students_by_name(students_list)
        
        context['students'] = students_sorted
        context['search'] = search
        context['sort_type'] = sort_type
        return context


class StudentCreateView(LoginRequiredMixin, TemplateView):
    """Create new student with optional password generation"""
    template_name = 'students/create.html'
    
    def post(self, request, *args, **kwargs):
        try:
            # Create new student with form data
            student = Student(
                student_id=request.POST.get('student_id'),
                first_name=request.POST.get('first_name'),
                last_name=request.POST.get('last_name'),
                email=request.POST.get('email'),
                phone_number=request.POST.get('phone_number', ''),
                program=request.POST.get('program'),
                current_semester=int(request.POST.get('current_semester')),
                admission_date=datetime.datetime.strptime(
                    request.POST.get('admission_date'), '%Y-%m-%d'
                ).date() if request.POST.get('admission_date') else None,
                batch=request.POST.get('batch', ''),
                roll_number=request.POST.get('roll_number', ''),
                address=request.POST.get('address', ''),
                emergency_contact_name=request.POST.get('emergency_contact_name', ''),
                emergency_contact_phone=request.POST.get('emergency_contact_phone', ''),
                notes=request.POST.get('notes', ''),
                is_active=bool(request.POST.get('is_active')),
                date_of_birth=datetime.datetime.strptime(
                    request.POST.get('date_of_birth'), '%Y-%m-%d'
                ).date() if request.POST.get('date_of_birth') else None,
                gender=request.POST.get('gender', ''),
            )
            
            student.save()
            
            # Create Django User account if password generation is requested
            if request.POST.get('create_account'):
                password = self.generate_password()
                user = User.objects.create_user(
                    email=student.email,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    password=password,
                    role='student'  # Set role to student
                )
                # Store the generated password to show to admin
                request.session['generated_password'] = password
                request.session['student_email'] = student.email
                messages.success(
                    request, 
                    f'Student {student.first_name} {student.last_name} added successfully! '
                    f'Account created with password: {password}'
                )
            else:
                messages.success(request, f'Student {student.first_name} {student.last_name} added successfully!')
            
            return redirect('students:list')
            
        except Exception as e:
            messages.error(request, f'Error creating student: {str(e)}')
            return self.get(request, *args, **kwargs)
    
    def generate_password(self):
        """Generate a random password for student"""
        length = 10
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for i in range(length))


class StudentUpdateView(LoginRequiredMixin, TemplateView):
    """Update existing student"""
    template_name = 'students/create.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            student = Student.objects.get(id=kwargs['pk'])
            context['student'] = student
        except DoesNotExist:
            messages.error(self.request, 'Student not found!')
            context['student'] = None
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            student = Student.objects.get(id=kwargs['pk'])
            
            # Update student fields
            student.student_id = request.POST.get('student_id')
            student.first_name = request.POST.get('first_name')
            student.last_name = request.POST.get('last_name')
            student.email = request.POST.get('email')
            student.phone_number = request.POST.get('phone_number', '')
            student.program = request.POST.get('program')
            student.current_semester = int(request.POST.get('current_semester'))
            
            if request.POST.get('admission_date'):
                student.admission_date = datetime.datetime.strptime(
                    request.POST.get('admission_date'), '%Y-%m-%d'
                ).date()
            
            student.batch = request.POST.get('batch', '')
            student.roll_number = request.POST.get('roll_number', '')
            student.address = request.POST.get('address', '')
            student.emergency_contact_name = request.POST.get('emergency_contact_name', '')
            student.emergency_contact_phone = request.POST.get('emergency_contact_phone', '')
            student.notes = request.POST.get('notes', '')
            student.is_active = bool(request.POST.get('is_active'))
            
            if request.POST.get('date_of_birth'):
                student.date_of_birth = datetime.datetime.strptime(
                    request.POST.get('date_of_birth'), '%Y-%m-%d'
                ).date()
            
            student.gender = request.POST.get('gender', '')
            
            student.save()
            messages.success(request, f'Student {student.first_name} {student.last_name} updated successfully!')
            return redirect('students:list')
            
        except DoesNotExist:
            messages.error(request, 'Student not found!')
            return redirect('students:list')
        except Exception as e:
            messages.error(request, f'Error updating student: {str(e)}')
            return self.get(request, *args, **kwargs)


class StudentDetailView(LoginRequiredMixin, TemplateView):
    """View student details with account info"""
    template_name = 'students/detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            student = Student.objects.get(id=kwargs['pk'])
            context['student'] = student
            
            # Check if student has a Django user account
            try:
                user = User.objects.get(email=student.email)
                context['has_account'] = True
                context['user_account'] = user
            except User.DoesNotExist:
                context['has_account'] = False
                context['user_account'] = None
                
        except DoesNotExist:
            messages.error(self.request, 'Student not found!')
            context['student'] = None
        return context


class StudentDeleteView(LoginRequiredMixin, TemplateView):
    """Delete student and associated account"""
    
    def post(self, request, *args, **kwargs):
        try:
            student = Student.objects.get(id=kwargs['pk'])
            student_name = f"{student.first_name} {student.last_name}"
            student_email = student.email
            
            # Delete associated Django user account if exists
            try:
                user = User.objects.get(email=student_email)
                user.delete()
            except User.DoesNotExist:
                pass
            
            student.delete()
            messages.success(request, f'Student {student_name} and associated account deleted successfully!')
        except DoesNotExist:
            messages.error(request, 'Student not found!')
        except Exception as e:
            messages.error(request, f'Error deleting student: {str(e)}')
        
        return redirect('students:list')


class StudentPasswordChangeView(LoginRequiredMixin, TemplateView):
    """Change student password (Admin only)"""
    template_name = 'students/password_change.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            student = Student.objects.get(id=kwargs['pk'])
            context['student'] = student
            
            # Check if student has account
            try:
                user = User.objects.get(email=student.email)
                context['has_account'] = True
                context['user_account'] = user
            except User.DoesNotExist:
                context['has_account'] = False
                context['user_account'] = None
                
        except DoesNotExist:
            messages.error(self.request, 'Student not found!')
            context['student'] = None
        return context
    
    def post(self, request, *args, **kwargs):
        try:
            student = Student.objects.get(id=kwargs['pk'])
            action = request.POST.get('action')
            
            if action == 'create_account':
                # Create new account
                password = self.generate_password()
                user = User.objects.create_user(
                    email=student.email,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    password=password,
                    role='student'
                )
                messages.success(
                    request, 
                    f'Account created for {student.first_name} {student.last_name}! '
                    f'Password: {password}'
                )
                
            elif action == 'change_password':
                # Change existing password
                try:
                    user = User.objects.get(email=student.email)
                    new_password = request.POST.get('new_password')
                    confirm_password = request.POST.get('confirm_password')
                    
                    if new_password != confirm_password:
                        messages.error(request, 'Passwords do not match!')
                        return self.get(request, *args, **kwargs)
                    
                    if len(new_password) < 8:
                        messages.error(request, 'Password must be at least 8 characters long!')
                        return self.get(request, *args, **kwargs)
                    
                    user.set_password(new_password)
                    user.save()
                    messages.success(
                        request, 
                        f'Password changed successfully for {student.first_name} {student.last_name}!'
                    )
                    
                except User.DoesNotExist:
                    messages.error(request, 'Student account not found!')
                    
            elif action == 'generate_password':
                # Generate new random password
                try:
                    user = User.objects.get(email=student.email)
                    new_password = self.generate_password()
                    user.set_password(new_password)
                    user.save()
                    messages.success(
                        request, 
                        f'New password generated for {student.first_name} {student.last_name}! '
                        f'Password: {new_password}'
                    )
                except User.DoesNotExist:
                    messages.error(request, 'Student account not found!')
            
            return redirect('students:password-change', pk=kwargs['pk'])
            
        except DoesNotExist:
            messages.error(request, 'Student not found!')
            return redirect('students:list')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return self.get(request, *args, **kwargs)
    
    def generate_password(self):
        """Generate a random password for student"""
        length = 10
        characters = string.ascii_letters + string.digits
        return ''.join(secrets.choice(characters) for i in range(length))


# ============================================================================
# ACTIVE/INACTIVE STATUS MANAGEMENT
# ============================================================================

@login_required
def toggle_student_status(request, pk):
    """Toggle student active/inactive status"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admins can change student status.')
        return redirect('students:list')
    
    try:
        student = Student.objects.get(id=pk)
        
        # Toggle status
        student.is_active = not student.is_active
        student.save()
        
        # Also update Django User account if exists
        try:
            user_account = User.objects.get(email=student.email)
            user_account.is_active = student.is_active
            user_account.save()
            
            status_text = "activated" if student.is_active else "deactivated"
            messages.success(request, f'Student {student.full_name} has been {status_text}.')
            
            if not student.is_active:
                messages.info(request, f'{student.full_name} will no longer be able to log in.')
                
        except User.DoesNotExist:
            status_text = "activated" if student.is_active else "deactivated"
            messages.success(request, f'Student {student.full_name} has been {status_text}.')
            
    except Student.DoesNotExist:
        messages.error(request, 'Student not found.')
    
    return redirect('students:detail', pk=pk)

@login_required 
def bulk_activate_students(request):
    """Bulk activate selected students"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admins can change student status.')
        return redirect('students:list')
    
    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        action = request.POST.get('action')
        
        if action == 'activate':
            activate = True
            action_text = 'activated'
        elif action == 'deactivate':
            activate = False
            action_text = 'deactivated'
        else:
            messages.error(request, 'Invalid action.')
            return redirect('students:list')
        
        count = 0
        for student_id in student_ids:
            try:
                student = Student.objects.get(id=student_id)
                student.is_active = activate
                student.save()
                
                # Update Django User account if exists
                try:
                    user_account = User.objects.get(email=student.email)
                    user_account.is_active = activate
                    user_account.save()
                except User.DoesNotExist:
                    pass
                
                count += 1
            except Student.DoesNotExist:
                continue
        
        messages.success(request, f'{count} students have been {action_text}.')
    
    return redirect('students:list')

@login_required
def bulk_update_semester(request):
    """Bulk update semester for selected students"""
    if request.user.role != 'admin':
        messages.error(request, 'Only admins can update student semesters.')
        return redirect('students:list')
    
    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        new_semester = request.POST.get('new_semester')
        
        if not new_semester:
            messages.error(request, 'Please select a target semester.')
            return redirect('students:list')
        
        if not student_ids:
            messages.error(request, 'Please select at least one student.')
            return redirect('students:list')
        
        try:
            new_semester = int(new_semester)
            if new_semester < 1 or new_semester > 8:
                messages.error(request, 'Invalid semester selected.')
                return redirect('students:list')
        except ValueError:
            messages.error(request, 'Invalid semester value.')
            return redirect('students:list')
        
        count = 0
        updated_students = []
        
        for student_id in student_ids:
            try:
                student = Student.objects.get(id=student_id)
                old_semester = student.current_semester
                student.current_semester = new_semester
                student.save()  # This will automatically sync enrollment via the save() method
                
                updated_students.append(f"{student.full_name} ({old_semester}→{new_semester})")
                count += 1
            except Student.DoesNotExist:
                continue
        
        if count > 0:
            semester_name = dict(Student.SEMESTER_CHOICES).get(new_semester)
            messages.success(
                request, 
                f'{count} student{"s" if count > 1 else ""} updated to {semester_name}.'
            )
            
            # Optional: Show detailed list if not too many students
            if count <= 10:
                detailed_message = "Updated students: " + ", ".join(updated_students)
                messages.info(request, detailed_message)
        else:
            messages.warning(request, 'No students were updated.')
    else:
        # Handle non-POST requests
        messages.error(request, 'Invalid request method.')
    
    return redirect('students:list')


# ============================================================================
# REST API VIEWSETS
# ============================================================================

class StudentViewSet(viewsets.ViewSet):
    """REST API for Student management"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """List all students"""
        try:
            students = Student.objects.all()
            serializer = StudentSerializer(students, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request):
        """Create new student"""
        try:
            serializer = StudentSerializer(data=request.data)
            if serializer.is_valid():
                student = Student(**serializer.validated_data)
                student.save()
                return Response(
                    StudentSerializer(student).data, 
                    status=status.HTTP_201_CREATED
                )
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def retrieve(self, request, pk=None):
        """Get specific student"""
        try:
            student = Student.objects.get(id=pk)
            serializer = StudentSerializer(student)
            return Response(serializer.data)
        except DoesNotExist:
            return Response(
                {'error': 'Student not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, pk=None):
        """Update student"""
        try:
            student = Student.objects.get(id=pk)
            serializer = StudentSerializer(data=request.data)
            if serializer.is_valid():
                for field, value in serializer.validated_data.items():
                    setattr(student, field, value)
                student.save()
                return Response(StudentSerializer(student).data)
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except DoesNotExist:
            return Response(
                {'error': 'Student not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, pk=None):
        """Delete student"""
        try:
            student = Student.objects.get(id=pk)
            student.delete()
            return Response(
                {'message': 'Student deleted successfully'}, 
                status=status.HTTP_204_NO_CONTENT
            )
        except DoesNotExist:
            return Response(
                {'error': 'Student not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search students by various fields including phone number"""
        try:
            query = request.query_params.get('q', '')
            if query:
                students = Student.objects.filter(
                    Q(first_name__icontains=query) |
                    Q(last_name__icontains=query) |
                    Q(email__icontains=query) |
                    Q(student_id__icontains=query) |
                    Q(phone_number__icontains=query)
                )
            else:
                students = Student.objects.all()
            
            serializer = StudentSerializer(students, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def by_program(self, request):
        """Get students by program"""
        try:
            program = request.query_params.get('program', '')
            if program:
                students = Student.objects.filter(program=program)
            else:
                students = Student.objects.all()
            
            serializer = StudentSerializer(students, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class StudentDocumentViewSet(viewsets.ViewSet):
    """REST API for Student Documents"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """List all student documents"""
        try:
            documents = StudentDocument.objects.all()
            serializer = StudentDocumentSerializer(documents, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def create(self, request):
        """Upload new document"""
        try:
            serializer = StudentDocumentSerializer(data=request.data)
            if serializer.is_valid():
                document = StudentDocument(**serializer.validated_data)
                document.save()
                return Response(
                    StudentDocumentSerializer(document).data, 
                    status=status.HTTP_201_CREATED
                )
            return Response(
                serializer.errors, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================================================
# UTILITY FUNCTIONS AND API ENDPOINTS
# ============================================================================

def get_student_statistics():
    """Get statistics about students"""
    try:
        total_students = Student.objects.count()
        active_students = Student.objects.filter(is_active=True).count()
        inactive_students = total_students - active_students
        
        # Count by program
        programs = {}
        for program in ['BCA', 'BIT', 'MBA', 'MCA']:
            programs[program] = Student.objects.filter(program=program).count()
        
        # Count by semester
        semesters = {}
        for semester in range(1, 9):
            semesters[f'Semester {semester}'] = Student.objects.filter(
                current_semester=semester
            ).count()
        
        return {
            'total_students': total_students,
            'active_students': active_students,
            'inactive_students': inactive_students,
            'programs': programs,
            'semesters': semesters
        }
    except Exception as e:
        return {'error': str(e)}


@login_required
def student_dashboard_stats(request):
    """API endpoint for dashboard statistics"""
    if request.method == 'GET':
        stats = get_student_statistics()
        return JsonResponse(stats)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def random_forest_analysis_view(request):
    """
    🤖 RANDOM FOREST ALGORITHM ANALYSIS
    Machine Learning for Student Performance Prediction
    
    Features:
    - Pass/Fail Prediction
    - Grade Performance Analysis (High/Medium/Low)
    - Attendance Risk Assessment
    - Feature Importance Analysis
    """
    
    if request.method == 'POST':
        # Run the Random Forest analysis only when form is submitted
        try:
            print("🚀 Starting Random Forest Analysis...")
            
            # Run the analysis
            analysis_result = run_random_forest_analysis()
            
            if not analysis_result['success']:
                messages.error(request, f"❌ {analysis_result['message']}")
            
            # Pass results to template
            context = {
                'analysis_completed': True,
                'analysis_result': analysis_result,
                'show_results': True
            }
            
            return render(request, 'students/random_forest_analysis.html', context)
            
        except Exception as e:
            print(f"❌ Random Forest Analysis Error: {e}")
            messages.error(request, f"Analysis failed: {str(e)}")
            return render(request, 'students/random_forest_analysis.html', {
                'analysis_completed': False,
                'error': str(e)
            })
    
    # For GET requests (including refresh), show clean initial page
    return render(request, 'students/random_forest_analysis.html', {
        'analysis_completed': False,
        'show_results': False
    })


@login_required
def kmeans_clustering_view(request):
    """
    🎯 K-MEANS CLUSTERING ALGORITHM ANALYSIS
    Machine Learning for Student Performance Clustering
    
    Features:
    - Student Performance Clustering
    - High/Medium/Low Performer Groups
    - Attendance & Academic Analysis
    - Assignment Completion Clustering
    """
    
    if request.method == 'POST':
        try:
            print("🎯 Starting K-Means Clustering Analysis...")
            
            analysis_result = run_kmeans_clustering()
            
            if not analysis_result['success']:
                messages.error(request, f"❌ {analysis_result['message']}")
            
            context = {
                'analysis_completed': True,
                'analysis_result': analysis_result,
                'show_results': True
            }
            
            return render(request, 'students/kmeans_clustering.html', context)
            
        except Exception as e:
            print(f"❌ K-Means Clustering Analysis Error: {e}")
            messages.error(request, f"Clustering analysis failed: {str(e)}")
            return render(request, 'students/kmeans_clustering.html', {
                'analysis_completed': False,
                'error': str(e)
            })
    
    return render(request, 'students/kmeans_clustering.html', {
        'analysis_completed': False,
        'show_results': False
    })


