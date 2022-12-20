from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View
from django.contrib.auth import authenticate, login, logout
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView, PasswordResetCompleteView, PasswordResetDoneView
from django.contrib import messages

from . mixins import LogoutRequiredMixin
from . senders import Util, email_verification_generate_token
from . forms import CustomPasswordResetForm, CustomSetPasswordForm, CustomUserCreationForm
import json

User = get_user_model()

class RegisterView(LogoutRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        print(request.session.get('name'))
        form = CustomUserCreationForm()

        context = {'form': form}
        return render(request, "accounts/register.html", context)

    def post(self, request, *args, **kwargs):
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            Util.send_verification_email(request, user)
            messages.success(request, 'Registration successful', extra_tags='toast')
            return render(request, 'accounts/email-activation-request.html', {'detail':'sent', 'email':user.email})
        
        return render(request, "accounts/register.html", {'form': form})

class VerifyEmail(LogoutRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user_id = kwargs.get('user_id')
        try:
            user_obj = User.objects.get(id = user_id)
        except:
            messages.error(request, 'You entered an invalid link')
            return redirect(reverse('login'))
        
        try:
            uid = force_str(urlsafe_base64_decode(kwargs.get('uidb64')))
            user = User.objects.get(id=uid)
        except Exception as e:
            user = None

        if user:
            if user_obj.id != user.id:
                messages.error(request, 'You entered an invalid link')
                return redirect(reverse('login'))

            if email_verification_generate_token.check_token(user, kwargs.get('token')):
                user.is_email_verified = True
                user.save()
                if not user.is_phone_verified:
                    Util.send_sms_otp(user)
                    request.session['verification_phone'] = user.phone
                    messages.success(request, 'Activation successful!. Verify your phone now!')
                    return redirect(reverse('verify-phone'))

                messages.success(request, 'Activation successful!. You can login now!')
                Util.send_welcome_email(request, user)
                return redirect(reverse("login"))

        return render(request, 'accounts/email-activation-failed.html', {"email": user_obj.email})

class ResendActivationEmail(LogoutRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        email = request.COOKIES.get('activation_email')
        user = User.objects.filter(email=email)
        if not user.exists():
            messages.error(request, 'Something went wrong')
            return redirect(reverse('login'))
        user = user.first()
        if user.is_email_verified:
            messages.warning(request, 'Email address already verified')
            return redirect(reverse('login'))

        Util.send_verification_email(request, user)
        return render(request, 'accounts/email-activation-request.html', {'detail':'resent', 'email':email})

class LoginView(LogoutRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, "accounts/login.html")

    def post(self, request, *args, **kwargs):
        email_or_phone = request.POST.get('email_or_phone')
        password = request.POST.get('password')
        user = authenticate(request, username=email_or_phone, password=password)
        if not user:
            messages.error(request, 'Invalid credentials', extra_tags='toast')
            return redirect('/accounts/login/')

        if not user.is_email_verified:
            Util.send_verification_email(request, user)
            return render(request, 'accounts/email-activation-request.html', {'detail':'request', 'email':user.email})

        if not user.is_phone_verified:
            Util.send_sms_otp(user)
            request.session['verification_phone'] = user.phone
            return redirect(reverse('verify-phone'))

        login(request, user)
        return redirect('/')

class LogoutView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect(reverse('login'))

class CustomPasswordResetView(LogoutRequiredMixin, PasswordResetView):
    # Taken from django.contrib.auth.views
    form_class = CustomPasswordResetForm

class CustomPasswordResetConfirmView(LogoutRequiredMixin, PasswordResetConfirmView):
    # Taken from django.contrib.auth.views
    form_class = CustomSetPasswordForm

class CustomPasswordResetDoneView(LogoutRequiredMixin, PasswordResetDoneView):
    # This is unnecessary as it can be done in the urls. Its just so that I can pass in Logout Required Mixin Easily
    # Taken from django.contrib.auth.views
    template_name="accounts/password-reset-sent.html"

class CustomPasswordResetCompleteView(LogoutRequiredMixin, PasswordResetCompleteView):
    # This is unnecessary as it can be done in the urls. Its just so that I can pass in Logout Required Mixin Easily
    # Taken from django.contrib.auth.views
    template_name="accounts/password-reset-done.html"
