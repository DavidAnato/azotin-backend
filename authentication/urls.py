from django.urls import path
from .views import *

urlpatterns = [
    path('register/', UserRegisterView.as_view(), name='user-register'),
    path('email-validate-request/', EmailValidateRequestView.as_view(), name='email-validate-request'),
    path('email-activate/', EmailActivateView.as_view(), name='email-activate'),
    path('login/', LoginView.as_view(), name='login'),
    path('google-login/', GoogleLoginView.as_view(), name='google-login'),
    path('pin-login/', PINLoginView.as_view(), name='pin-login'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('set-password/', SetPasswordView.as_view(), name='set-password'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('user-profile/', UserProfileView.as_view(), name='user-profile'),
    path('phone-number-validate-request/', PhoneNumberValidateRequestView.as_view(), name='phone-number-validate-request'),
    path('phone-number-validate-confirm/', PhoneNumberValidateConfirmView.as_view(), name='phone-number-validate-confirm'),
    path('code-pin-create/', CodePINCreateView.as_view(), name='code-pin-create'),
    path('code-pin-update/', CodePINUpdateView.as_view(), name='code-pin-update'),
    path('check-phone-number/', CheckPhoneNumberView.as_view(), name='check-phone-number'),
]