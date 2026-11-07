from decimal import Decimal
from django import forms
from django.contrib.auth import authenticate
from .models import User, ActivationCode, Transaction, KYCDocument


class UserRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, min_length=6, required=True)
    activation_code = forms.CharField(max_length=6, min_length=6, required=True)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('البريد الإلكتروني مسجل مسبقاً، يرجى تسجيل الدخول.')
        return email

    def clean_activation_code(self):
        code = self.cleaned_data['activation_code'].strip().upper()
        if len(code) != 6:
            raise forms.ValidationError('كود التفعيل يجب أن يتكون من 6 محارف بالضبط!')
        if not ActivationCode.objects.filter(code=code, is_used=False).exists():
            raise forms.ValidationError('كود التفعيل غير صالح أو تم استخدامه مسبقاً!')
        return code


class UserLoginForm(forms.Form):
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    def __init__(self, *args, **kwargs):
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email', '').strip().lower()
        password = cleaned_data.get('password', '')

        if email and password:
            user_obj = User.objects.filter(email__iexact=email).first()
            if user_obj:
                self.user_cache = authenticate(username=user_obj.username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError('البريد الإلكتروني أو كلمة المرور غير صحيحة!')
            if self.user_cache.is_banned:
                raise forms.ValidationError('تم تجميد حسابك من قبل الإدارة!')
        return cleaned_data

    def get_user(self):
        return self.user_cache


class AdminLoginForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)

    def __init__(self, *args, **kwargs):
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get('username', '').strip()
        password = cleaned_data.get('password', '')

        if identifier and password:
            user_obj = User.objects.filter(username__iexact=identifier).first()
            if not user_obj:
                user_obj = User.objects.filter(email__iexact=identifier).first()

            if user_obj:
                self.user_cache = authenticate(username=user_obj.username, password=password)

            if self.user_cache is None:
                raise forms.ValidationError('بيانات الدخول غير صحيحة!')
            if not (self.user_cache.is_staff or self.user_cache.is_superuser):
                raise forms.ValidationError('ليس لديك صلاحيات الإدارة للوصول إلى مركز التحكم!')
        return cleaned_data

    def get_user(self):
        return self.user_cache


class DepositForm(forms.Form):
    NETWORK_CHOICES = [
        ('TRC20', 'Tron (TRC20) - الأسرع'),
        ('BEP20', 'BNB Smart Chain (BEP20)'),
    ]
    network = forms.ChoiceField(choices=NETWORK_CHOICES, required=True)
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('1.00'), required=True)
    proof_image = forms.ImageField(required=True)

    def clean_amount(self):
        amt = self.cleaned_data['amount']
        if amt <= 0:
            raise forms.ValidationError('يرجى إدخال مبلغ إيداع صحيح!')
        return amt


class WithdrawForm(forms.Form):
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('1.00'), required=True)
    wallet_address = forms.CharField(max_length=255, required=True)

    def clean_wallet_address(self):
        addr = self.cleaned_data['wallet_address'].strip()
        if len(addr) < 10:
            raise forms.ValidationError('يرجى إدخال عنوان محفظة USDT صحيح!')
        return addr


class KYCSubmissionForm(forms.Form):
    full_name = forms.CharField(max_length=150, required=True)
    dob = forms.DateField(required=True)
    address = forms.CharField(max_length=255, required=True)
    doc_number = forms.CharField(max_length=100, required=True)
    front_id_img = forms.ImageField(required=False)
    back_id_img = forms.ImageField(required=False)
