# accounts/views.py - Enhanced with admin password management and admin-only profile editing

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, UpdateView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy, reverse
from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .models import User, UserProfile
from .serializers import UserSerializer, UserProfileSerializer
import string
import secrets


# ==================== WEB AUTHENTICATION VIEWS ====================

class CustomLoginView(LoginView):
    """Custom login view with enhanced messaging and redirect logic"""
    template_name = 'registration/login.html'
    form_class = AuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        """Role-based redirect after successful login"""
        user = self.request.user
        if hasattr(user, 'role'):
            if user.role == 'admin':
                return reverse('admin_dashboard')
            elif user.role == 'teacher':
                return reverse('courses:teacher-dashboard')
            elif user.role == 'student':
                return reverse('courses:student-dashboard')
        return reverse('dashboard')

    def form_valid(self, form):
        """Handle successful login with role-based messaging"""
        response = super().form_valid(form)
        user = form.get_user()
        user_name = user.full_name or user.email

        messages.success(
            self.request,
            f'Welcome back, {user_name}! You are logged in as {user.role.title()}.',
            extra_tags='auto-dismiss'
        )
        return response

    def form_invalid(self, form):
        """Handle failed login with helpful messaging"""
        # Check if the failure is due to an inactive account
        username = form.cleaned_data.get('username')
        if username:
            try:
                user = User.objects.get(email=username)
                if not user.is_active:
                    messages.error(
                        self.request,
                        'Your account has been deactivated. Please contact the administrator.'
                    )
                    return super().form_invalid(form)
            except User.DoesNotExist:
                pass

        messages.error(
            self.request,
            'Invalid email or password. Please check your credentials and try again.'
        )
        return super().form_invalid(form)

class CustomLogoutView(LogoutView):
    """Custom logout view with messaging"""
    next_page = reverse_lazy('accounts:login')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            user_name = request.user.full_name or request.user.email
            messages.success(request, f'You have been successfully logged out. Goodbye, {user_name}!', extra_tags='auto-dismiss')
        return super().dispatch(request, *args, **kwargs)


# ==================== PROFILE MANAGEMENT VIEWS ====================

class ProfileView(LoginRequiredMixin, TemplateView):
    """User profile view with role-based information"""
    template_name = 'accounts/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        
        # Get MongoDB profile if exists
        try:
            profile = UserProfile.objects.get(user_id=str(self.request.user.id))
            context['profile'] = profile
        except UserProfile.DoesNotExist:
            context['profile'] = None
            
        return context


class ProfileEditView(LoginRequiredMixin, TemplateView):
    """Edit user profile information - ADMIN ONLY"""
    template_name = 'accounts/profile_edit.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Restrict access to admins only"""
        if request.user.role != 'admin':
            messages.error(request, 'Access denied. Only administrators can edit profiles.')
            return redirect('accounts:profile')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle profile updates - Admin only"""
        if request.user.role != 'admin':
            messages.error(request, 'Access denied. Only administrators can edit profiles.')
            return redirect('accounts:profile')
        
        user = request.user
        
        # Update Django User fields
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.save()
        
        # Update or create MongoDB profile
        try:
            profile = UserProfile.objects.get(user_id=str(user.id))
        except UserProfile.DoesNotExist:
            profile = UserProfile(user_id=str(user.id), email=user.email, role=user.role)
        
        profile.first_name = request.POST.get('first_name', '')
        profile.last_name = request.POST.get('last_name', '')
        profile.phone = request.POST.get('phone', '')
        profile.address = request.POST.get('address', '')
        profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('accounts:profile')


# ==================== DASHBOARD ROUTING ====================

class DashboardView(LoginRequiredMixin, TemplateView):
    """Role-based dashboard routing"""
    
    def get_template_names(self):
        user = self.request.user
        if hasattr(user, 'role'):
            if user.role == 'admin':
                return ['dashboard/admin.html']
            elif user.role == 'teacher':
                return ['dashboard/teacher.html']
            elif user.role == 'student':
                return ['dashboard/student.html']
        return ['dashboard/main.html']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context


# ==================== ADMIN PASSWORD MANAGEMENT ====================

class AdminPasswordManagementView(LoginRequiredMixin, TemplateView):
    """Admin-only view for managing user passwords"""
    template_name = 'accounts/admin_password_management.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff and request.user.role != 'admin':
            messages.error(request, 'Access denied. Admin privileges required.')
            return redirect('dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all users for password management
        context['teachers'] = User.objects.filter(role='teacher').order_by('first_name', 'last_name')
        context['students'] = User.objects.filter(role='student').order_by('first_name', 'last_name')
        
        return context


@login_required
def change_user_password(request, user_id):
    """Admin function to change any user's password"""
    if not request.user.is_staff and request.user.role != 'admin':
        messages.error(request, 'Access denied. Admin privileges required.')
        return redirect('dashboard')
    
    target_user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'set_password':
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')
            
            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match!')
                return redirect('accounts:admin-password-management')
            
            if len(new_password) < 8:
                messages.error(request, 'Password must be at least 8 characters long!')
                return redirect('accounts:admin-password-management')
            
            target_user.set_password(new_password)
            target_user.save()
            
            messages.success(
                request, 
                f'Password changed successfully for {target_user.full_name or target_user.email}!'
            )
            
        elif action == 'generate_password':
            new_password = generate_random_password()
            target_user.set_password(new_password)
            target_user.save()
            
            messages.success(
                request, 
                f'New password generated for {target_user.full_name or target_user.email}: {new_password}'
            )
    
    return redirect('accounts:admin-password-management')


def generate_random_password(length=10):
    """Generate a secure random password with mixed character types"""
    # Ensure at least one of each type
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]
    characters = string.ascii_letters + string.digits
    password += [secrets.choice(characters) for _ in range(length - 3)]
    # Shuffle to avoid predictable positions
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    return ''.join(password_list)


# ==================== UTILITY VIEWS ====================

@login_required
def change_own_password(request):
    """Allow users to change their own password - Admin only for profile editing"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect!')
            return redirect('accounts:profile')
        
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match!')
            return redirect('accounts:profile')
        
        if len(new_password) < 8:
            messages.error(request, 'Password must be at least 8 characters long!')
            return redirect('accounts:profile')
        
        request.user.set_password(new_password)
        request.user.save()
        
        # Re-authenticate user to maintain session
        user = authenticate(request, username=request.user.email, password=new_password)
        if user:
            login(request, user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('accounts:profile')
    
    return redirect('accounts:profile')


# ==================== API VIEWSETS ====================

class UserViewSet(viewsets.ViewSet):
    """REST API for User management"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        # Only admin can list all users
        if request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=403)
        
        users = User.objects.all().order_by('role', 'first_name', 'last_name')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        try:
            user = User.objects.get(pk=pk)
            
            # Users can only see their own data unless they're admin
            if request.user.role != 'admin' and request.user.id != user.id:
                return Response({'error': 'Access denied'}, status=403)
            
            serializer = UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)


class UserProfileViewSet(viewsets.ViewSet):
    """REST API for User Profiles"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        if request.user.role != 'admin':
            return Response({'error': 'Admin access required'}, status=403)
        
        profiles = UserProfile.objects.all()
        serializer = UserProfileSerializer(profiles, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        try:
            profile = UserProfile.objects.get(user_id=pk)
            
            # Users can only see their own profile unless they're admin
            if request.user.role != 'admin' and str(request.user.id) != pk:
                return Response({'error': 'Access denied'}, status=403)
            
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=404)


class CurrentUserView(APIView):
    """API view for current user information"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """API view for password changes"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        if not user.check_password(old_password):
            return Response({'error': 'Invalid old password'}, status=400)
        
        if len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters long'}, status=400)
        
        user.set_password(new_password)
        user.save()
        
        return Response({'message': 'Password changed successfully'})


# ==================== LEGACY VIEWS (for compatibility) ====================

class RoleSelectionView(LoginRequiredMixin, TemplateView):
    """Legacy role selection view (redirect to dashboard)"""
    
    def get(self, request, *args, **kwargs):
        return redirect('dashboard')