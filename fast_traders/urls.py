from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from core import views

urlpatterns = [
    path('django-internal-admin/', admin.site.urls),

    path('', views.index_view, name='index'),
    path('register/', views.register_view, name='register'),
    path('login/', views.user_login_view, name='login'),
    path('logout/', views.user_logout_view, name='logout'),

    path('control-panel/login/', views.admin_login_view, name='admin_login'),
    path('control-panel/logout/', views.admin_logout_view, name='admin_logout'),
    path('control-panel/generate-codes/', views.admin_generate_codes_view, name='admin_generate_codes'),
    path('control-panel/', views.admin_panel_view, name='admin_panel'),

    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('markets/', views.markets_view, name='markets'),
    path('wallet/', views.wallet_view, name='wallet'),
    path('kyc/', views.kyc_view, name='kyc'),
    path('terminal/', views.terminal_view, name='terminal'),
    path('api/execute-trade/', views.execute_trade_api, name='execute_trade_api'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
