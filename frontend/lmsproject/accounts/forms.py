from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import StudentProfile # Keep existing imports

class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, help_text='Required. Inform a valid email address.', required=True)

    class Meta:
        model = User
        fields = ('email',)

    def save(self, commit=True):
            # Call the parent save method but don't commit to DB yet
            # This handles password hashing etc.
            user = super().save(commit=False)

            # Set the username to the email
            user.email = self.cleaned_data['email'] # Ensure email field is also set if not done by super()
            user.username = self.cleaned_data['email'] # Set username = email

            if commit:
                # Before saving, you might want to add a check for username uniqueness
                # although database constraints often handle this.
                # Example check (optional):
                # if User.objects.filter(username=user.username).exists():
                #     raise forms.ValidationError("A user with this email already exists.")
                user.save()
            return user

        # Optional: Add clean_email method for uniqueness check earlier
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(username=email).exists():
            raise forms.ValidationError("A user with this email already exists (username conflict).")
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

class LoginForm(forms.Form):
    email = forms.EmailField(max_length=254, required=True)
    password = forms.CharField(widget=forms.PasswordInput)
    
    # def clean(self):
    #     username = self.cleaned_data.get("username")
    #     password = self.cleaned_data.get("password")
    #     user = authenticate(username=username, password=password)
    #     if not user:
    #         raise forms.ValidationError("Invalid login credentials")
    #     return self.cleaned_data
