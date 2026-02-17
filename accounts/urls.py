# accounts/urls.py - Clean URL patterns for admin-only authentication

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# API Router
router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'profiles', views.UserProfileViewSet, basename='profile')

app_name = 'accounts'

urlpatterns = [
    # ==================== AUTHENTICATION URLS ====================
    # Login/Logout (replaces allauth)
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    
    # ==================== PROFILE MANAGEMENT ====================
    # User profile management
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile-edit'),
    path('profile/change-password/', views.change_own_password, name='change-own-password'),
    
    # ==================== ADMIN PASSWORD MANAGEMENT ====================
    # Admin-only password management
    path('admin/passwords/', views.AdminPasswordManagementView.as_view(), name='admin-password-management'),
    path('admin/change-password/<int:user_id>/', views.change_user_password, name='change-user-password'),
    
    # ==================== DASHBOARD ROUTING ====================
    # Dashboard and role management
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('role-selection/', views.RoleSelectionView.as_view(), name='role-selection'),  # Legacy support
    
    # ==================== API ENDPOINTS ====================
    # REST API URLs
    path('api/', include(router.urls)),
    path('api/current-user/', views.CurrentUserView.as_view(), name='current-user'),
    path('api/change-password/', views.ChangePasswordView.as_view(), name='api-change-password'),
]