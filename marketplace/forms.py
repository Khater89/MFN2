from pathlib import Path
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile, Product, Service, MarketplacePolicy

class RegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=120, label='Full name / pharmacy name')
    email = forms.EmailField()
    role = forms.ChoiceField(choices=Profile.ROLES)
    city = forms.CharField(max_length=80)
    class Meta:
        model = User
        fields = ['username','full_name','email','role','city','password1','password2']
    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists(): raise forms.ValidationError('An account already uses this email.')
        return email

class OnboardingForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    class Meta:
        model = Profile
        fields = ['display_name','phone','city','specialty','bio','service_areas','license_number','license_document','revision']
        widgets = {'bio': forms.Textarea(attrs={'rows':3})}
    def clean_license_document(self):
        document = self.cleaned_data.get('license_document')
        if not document: raise forms.ValidationError('Upload a license document for private admin review.')
        if hasattr(document, 'content_type'):
            ext = Path(document.name).suffix.lower()
            if ext not in ['.pdf','.png','.jpg','.jpeg']: raise forms.ValidationError('Use a PDF, PNG or JPEG file.')
            if document.size > 5 * 1024 * 1024: raise forms.ValidationError('Maximum file size is 5 MB.')
            head = document.read(8); document.seek(0)
            valid = (ext == '.pdf' and head.startswith(b'%PDF-')) or (ext == '.png' and head.startswith(b'\x89PNG\r\n\x1a\n')) or (ext in ['.jpg','.jpeg'] and head.startswith(b'\xff\xd8\xff'))
            if not valid: raise forms.ValidationError('The file content does not match its extension.')
        return document
    def clean_service_areas(self):
        value = self.cleaned_data['service_areas'].strip()
        if not value: raise forms.ValidationError('Add at least one city you serve.')
        return value
    def clean_license_number(self):
        value = self.cleaned_data['license_number'].strip()
        if not value: raise forms.ValidationError('Enter your license number.')
        return value

class CheckoutForm(forms.Form):
    quote = forms.CharField(widget=forms.HiddenInput)
    city = forms.CharField(max_length=80, label='Service / delivery city')
    address = forms.CharField(max_length=250, label='Full address', widget=forms.Textarea(attrs={'rows':2}))
    slot = forms.ChoiceField(required=False, label='Appointment time')
    quantity = forms.IntegerField(min_value=1, max_value=50, initial=1)
    acknowledge = forms.BooleanField(label='I understand this submits an unpaid request. No payment is collected.')
    def clean_city(self): return self.cleaned_data['city'].strip()
    def clean_address(self):
        value = self.cleaned_data['address'].strip()
        if len(value) < 8: raise forms.ValidationError('Enter a complete address, including street and building.')
        return value

class ProductForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput, initial=0)
    class Meta:
        model = Product
        fields = ['name','category','description','price','currency','stock','active','revision']
        widgets = {'description':forms.Textarea(attrs={'rows':3})}
    def clean_currency(self):
        value = self.cleaned_data['currency'].upper()
        if len(value) != 3 or not value.isalpha(): raise forms.ValidationError('Use a three-letter currency code.')
        return value

class ServiceForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput, initial=0)
    class Meta:
        model = Service
        fields = ['title','category','description','price','currency','duration','active','revision']
        widgets = {'description':forms.Textarea(attrs={'rows':3})}
    def clean_currency(self):
        value = self.cleaned_data['currency'].upper()
        if len(value) != 3 or not value.isalpha(): raise forms.ValidationError('Use a three-letter currency code.')
        return value

class PolicyForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(label='I confirm this approved business rule: commission is deducted from merchant gross, with no patient surcharge. Applies to future transactions only.')
    class Meta:
        model = MarketplacePolicy
        fields = ['commission_percent','currency','revision']
    def clean_currency(self):
        value = self.cleaned_data['currency'].upper()
        if value and (len(value) != 3 or not value.isalpha()): raise forms.ValidationError('Use a three-letter currency code.')
        return value
