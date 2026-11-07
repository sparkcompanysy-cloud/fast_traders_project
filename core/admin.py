from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import PlatformSetting, User, ActivationCode, KYCDocument, Asset, Transaction, Trade


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'full_name', 'activation_code', 'real_balance', 'total_deposited', 'kyc_status', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Fast Traders Financial & Risk Profile', {
            'fields': (
                'full_name', 'activation_code', 'real_balance', 'demo_balance',
                'total_deposited', 'daily_profit', 'profit_cap', 'cap_type',
                'risk_mode', 'kyc_status', 'is_banned'
            )
        }),
    )


@admin.register(ActivationCode)
class ActivationCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_used', 'used_by', 'created_at', 'used_at')
    list_filter = ('is_used',)
    search_fields = ('code', 'used_by__email', 'used_by__full_name')


admin.site.register(PlatformSetting)
admin.site.register(KYCDocument)
admin.site.register(Asset)
admin.site.register(Transaction)
admin.site.register(Trade)
