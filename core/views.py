import uuid
import json
import random
from decimal import Decimal
from django.http import JsonResponse
from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.utils import timezone
from .models import User, ActivationCode, Asset, Transaction, Trade, KYCDocument, PlatformSetting
from .forms import (
    UserRegistrationForm,
    UserLoginForm,
    AdminLoginForm,
    DepositForm,
    WithdrawForm,
    KYCSubmissionForm,
)


def is_admin_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def index_view(request):
    assets = Asset.objects.all()[:4]
    return render(request, 'index.html', {'assets': assets})


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = UserRegistrationForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            email = form.cleaned_data['email']
            full_name = form.cleaned_data['full_name']
            password = form.cleaned_data['password']
            code_str = form.cleaned_data['activation_code']

            with transaction.atomic():
                # Lock the activation code row to prevent race conditions
                code_obj = ActivationCode.objects.select_for_update().filter(
                    code=code_str,
                    is_used=False
                ).first()

                if not code_obj:
                    messages.error(request, 'كود التفعيل غير صالح أو تم استخدامه للتو!')
                    return render(request, 'register.html', {'form': form})

                base_username = email.split('@')[0][:20]
                username = base_username
                while User.objects.filter(username__iexact=username).exists():
                    username = f"{base_username}_{uuid.uuid4().hex[:4]}"

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    full_name=full_name,
                    activation_code=code_str,
                    real_balance=Decimal('0.00'),
                    demo_balance=Decimal('10000.00'),
                )

                # Mark activation code as permanently used by this user
                code_obj.is_used = True
                code_obj.used_by = user
                code_obj.used_at = timezone.now()
                code_obj.save(update_fields=['is_used', 'used_by', 'used_at'])

            login(request, user)
            messages.success(request, 'تم تفعيل وإنشاء حسابك بنجاح! مرحباً بك في Fast Traders.')
            return redirect('dashboard')
        else:
            for field_errors in form.errors.values():
                for err in field_errors:
                    messages.error(request, err)

    return render(request, 'register.html', {'form': form})


@require_http_methods(["GET", "POST"])
def user_login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    form = UserLoginForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'تم تسجيل الدخول بنجاح!')
            return redirect('dashboard')
        else:
            for field_errors in form.errors.values():
                for err in field_errors:
                    messages.error(request, err)

    return render(request, 'login.html', {'form': form})


def user_logout_view(request):
    logout(request)
    messages.success(request, 'تم تسجيل الخروج بنجاح.')
    return redirect('index')


@require_http_methods(["GET", "POST"])
def admin_login_view(request):
    if is_admin_user(request.user):
        return redirect('admin_panel')

    form = AdminLoginForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            admin_user = form.get_user()
            login(request, admin_user)
            messages.success(request, f'مرحباً بك {admin_user.display_name}! تم فتح مركز القيادة.')
            return redirect('admin_panel')
        else:
            for field_errors in form.errors.values():
                for err in field_errors:
                    messages.error(request, err)

    return render(request, 'admin_login.html', {'form': form})


def admin_logout_view(request):
    logout(request)
    messages.success(request, 'تم قفل لوحة الإدارة وتسجيل الخروج بنجاح.')
    return redirect('admin_login')


# ==========================================
# TRADER PORTAL VIEWS
# ==========================================

@login_required(login_url='/login/')
def dashboard_view(request):
    recent_trades = Trade.objects.filter(user=request.user)[:6]
    return render(request, 'dashboard.html', {
        'active_nav': 'dashboard',
        'recent_trades': recent_trades,
    })


@login_required(login_url='/login/')
def markets_view(request):
    assets = Asset.objects.all()
    market_list = []
    for asset in assets:
        is_unlocked = (not asset.locked_by_admin) and (request.user.total_deposited >= asset.min_deposit)
        market_list.append({
            'asset': asset,
            'is_unlocked': is_unlocked,
        })
    return render(request, 'markets.html', {
        'active_nav': 'markets',
        'market_list': market_list,
    })


@login_required(login_url='/login/')
@require_http_methods(["GET", "POST"])
def wallet_view(request):
    platform_settings = PlatformSetting.get_solo()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'deposit':
            form = DepositForm(request.POST, request.FILES)
            if form.is_valid():
                Transaction.objects.create(
                    user=request.user,
                    tx_type='إيداع',
                    network=form.cleaned_data['network'],
                    amount=form.cleaned_data['amount'],
                    status='قيد المراجعة',
                    proof_image=form.cleaned_data['proof_image'],
                    wallet_address=form.cleaned_data['network'],
                )
                messages.success(request, 'تم إرسال طلب الإيداع وصورة الإيصال للإدارة للمراجعة!')
                return redirect('wallet')
            else:
                for field_errors in form.errors.values():
                    for err in field_errors:
                        messages.error(request, err)

        elif action == 'withdraw':
            form = WithdrawForm(request.POST)
            if form.is_valid():
                amt = form.cleaned_data['amount']
                addr = form.cleaned_data['wallet_address']
                with transaction.atomic():
                    locked_user = User.objects.select_for_update().get(pk=request.user.pk)
                    if amt > locked_user.real_balance:
                        messages.error(request, 'المبلغ المطلوب يتجاوز رصيدك الحقيقي المتاح للسحب!')
                    else:
                        locked_user.real_balance -= amt
                        locked_user.save(update_fields=['real_balance'])
                        Transaction.objects.create(
                            user=locked_user,
                            tx_type='سحب',
                            network='TRC20',
                            amount=amt,
                            status='قيد المراجعة',
                            wallet_address=addr,
                        )
                        messages.success(request, 'تم تقديم طلب السحب بنجاح وبانتظار موافقة الإدارة!')
                return redirect('wallet')
            else:
                for field_errors in form.errors.values():
                    for err in field_errors:
                        messages.error(request, err)

    transactions = Transaction.objects.filter(user=request.user)
    return render(request, 'wallet.html', {
        'active_nav': 'wallet',
        'platform_settings': platform_settings,
        'transactions': transactions,
    })


@login_required(login_url='/login/')
@require_http_methods(["GET", "POST"])
def kyc_view(request):
    kyc_doc = KYCDocument.objects.filter(user=request.user).first()

    if request.method == 'POST':
        form = KYCSubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            front_img = form.cleaned_data.get('front_id_img') or (kyc_doc.front_id_img if kyc_doc else None)
            back_img = form.cleaned_data.get('back_id_img') or (kyc_doc.back_id_img if kyc_doc else None)

            if not front_img or not back_img:
                messages.error(request, 'يرجى رفع صورتي الهوية الأمامية والخلفية!')
            else:
                if kyc_doc:
                    kyc_doc.full_name = form.cleaned_data['full_name']
                    kyc_doc.dob = form.cleaned_data['dob']
                    kyc_doc.address = form.cleaned_data['address']
                    kyc_doc.doc_number = form.cleaned_data['doc_number']
                    if form.cleaned_data.get('front_id_img'):
                        kyc_doc.front_id_img = form.cleaned_data['front_id_img']
                    if form.cleaned_data.get('back_id_img'):
                        kyc_doc.back_id_img = form.cleaned_data['back_id_img']
                    kyc_doc.save()
                else:
                    kyc_doc = KYCDocument.objects.create(
                        user=request.user,
                        full_name=form.cleaned_data['full_name'],
                        dob=form.cleaned_data['dob'],
                        address=form.cleaned_data['address'],
                        doc_number=form.cleaned_data['doc_number'],
                        front_id_img=front_img,
                        back_id_img=back_img,
                    )
                request.user.kyc_status = 'pending'
                request.user.save(update_fields=['kyc_status'])
                messages.success(request, 'تم إرسال بياناتك وصور الهوية للإدارة بنجاح!')
                return redirect('kyc')
        else:
            for field_errors in form.errors.values():
                for err in field_errors:
                    messages.error(request, err)

    return render(request, 'kyc.html', {
        'active_nav': 'kyc',
        'kyc_doc': kyc_doc,
    })


# ==========================================
# ADMIN CODE GENERATOR ENDPOINT
# ==========================================

@user_passes_test(is_admin_user, login_url='/control-panel/login/')
@require_POST
def admin_generate_codes_view(request):
    try:
        quantity = int(request.POST.get('quantity', 1))
    except (TypeError, ValueError):
        quantity = 1

    if quantity < 1 or quantity > 500:
        messages.error(request, 'يرجى تحديد عدد أكواد بين 1 و 500 في المرة الواحدة.')
    else:
        new_codes = ActivationCode.generate_codes(quantity)
        codes_preview = ', '.join(c.code for c in new_codes[:5])
        if len(new_codes) > 5:
            codes_preview += ' ...'
        messages.success(request, f'تم توليد {len(new_codes)} كود تفعيل جديد بنجاح: ({codes_preview})')

    return redirect('admin_panel')


@login_required(login_url='/login/')
def terminal_view(request):
    assets = Asset.objects.all()
    default_asset = assets.first()
    return render(request, 'terminal.html', {
        'active_nav': 'terminal',
        'assets': assets,
        'default_asset': default_asset,
    })


@login_required(login_url='/login/')
@require_POST
def execute_trade_api(request):
    """Secure backend API for executing binary option trades and applying Admin Risk Modes."""
    try:
        data = json.loads(request.body)
        asset_id = data.get('asset_id')
        direction = data.get('direction')  # 'CALL' or 'PUT'
        amount = Decimal(str(data.get('amount', '10')))
        duration = int(data.get('duration', 3))
        account_type = data.get('account_type', 'real')  # 'real' or 'demo'

        if direction not in ('CALL', 'PUT'):
            return JsonResponse({'success': False, 'error': 'اتجاه الصفقة غير صالح.'}, status=400)
        if amount <= 0:
            return JsonResponse({'success': False, 'error': 'مبلغ الصفقة غير صالح.'}, status=400)

        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            if user.is_banned:
                return JsonResponse({'success': False, 'error': 'تم تجميد حسابك من قبل الإدارة.'}, status=403)

            asset = Asset.objects.filter(id=asset_id).first()
            if not asset:
                return JsonResponse({'success': False, 'error': 'الأصل المالي غير موجود.'}, status=404)

            if asset.locked_by_admin:
                return JsonResponse({'success': False, 'error': f'زوج {asset.symbol} مقفول حالياً من قبل الإدارة.'}, status=400)

            if account_type == 'real' and user.total_deposited < asset.min_deposit:
                return JsonResponse({
                    'success': False,
                    'error': f'يتطلب التداول الحقيقي على {asset.symbol} إيداعاً لا يقل عن ${asset.min_deposit}.'
                }, status=400)

            cur_bal = user.real_balance if account_type == 'real' else user.demo_balance
            if amount > cur_bal:
                return JsonResponse({'success': False, 'error': 'الرصيد غير كافٍ لفتح هذه الصفقة.'}, status=400)

            # Deduct stake immediately
            if account_type == 'real':
                user.real_balance -= amount
                user.save(update_fields=['real_balance'])
            else:
                user.demo_balance -= amount
                user.save(update_fields=['demo_balance'])

            # Calculate potential profit
            profit_payout = amount * (Decimal(str(asset.payout)) / Decimal('100.00'))

            # Determine win/loss based on Admin Risk Modulator & Profit Cap
            is_win = (random.random() >= 0.45)
            if account_type == 'real':
                max_allowed_cap = user.effective_profit_cap
                if user.risk_mode == 'house_edge':
                    is_win = False
                elif user.risk_mode == 'capped':
                    if (user.daily_profit + profit_payout) > max_allowed_cap or user.daily_profit >= max_allowed_cap:
                        is_win = False
                    else:
                        is_win = True

            result_amt = profit_payout if is_win else -amount

            # Credit payout if win
            if is_win:
                total_return = amount + profit_payout
                if account_type == 'real':
                    user.real_balance += total_return
                    user.daily_profit += profit_payout
                    user.save(update_fields=['real_balance', 'daily_profit'])
                else:
                    user.demo_balance += total_return
                    user.save(update_fields=['demo_balance'])
            else:
                if account_type == 'real':
                    user.daily_profit -= amount
                    user.save(update_fields=['daily_profit'])

            # Log trade
            trade_obj = Trade.objects.create(
                user=user,
                asset=asset,
                symbol=asset.symbol,
                account_type=account_type,
                direction=direction,
                amount=amount,
                duration=duration,
                is_win=is_win,
                result_amount=result_amt,
            )

            return JsonResponse({
                'success': True,
                'is_win': is_win,
                'profit': float(profit_payout),
                'result_amount': float(result_amt),
                'new_real_balance': float(user.real_balance),
                'new_demo_balance': float(user.demo_balance),
                'new_daily_profit': float(user.daily_profit),
            })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



@user_passes_test(is_admin_user, login_url='/control-panel/login/')
@require_http_methods(["GET", "POST"])
def admin_panel_view(request):
    platform_settings = PlatformSetting.get_solo()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'delete_code':
            ActivationCode.objects.filter(id=request.POST.get('code_id'), is_used=False).delete()
            messages.success(request, 'تم حذف كود التفعيل بنجاح.')

        elif action == 'update_user_balance':
            u = User.objects.filter(id=request.POST.get('user_id')).first()
            if u:
                u.real_balance = Decimal(request.POST.get('real_balance', '0') or '0')
                u.total_deposited = Decimal(request.POST.get('total_deposited', '0') or '0')
                u.is_banned = ('is_banned' in request.POST)
                u.save(update_fields=['real_balance', 'total_deposited', 'is_banned'])
                messages.success(request, f'تم تحديث رصيد وحالة المتداول #{u.id} بنجاح!')

        elif action == 'kyc_decision':
            u = User.objects.filter(id=request.POST.get('user_id')).first()
            decision = request.POST.get('decision')
            if u and decision in ('approved', 'rejected'):
                u.kyc_status = decision
                u.save(update_fields=['kyc_status'])
                messages.success(request, f'تم تحديث حالة التوثيق للمتداول #{u.id} إلى {decision}.')

        elif action == 'save_wallets':
            platform_settings.deposit_wallet_trc20 = request.POST.get('wallet_trc20', '').strip()
            platform_settings.deposit_wallet_bep20 = request.POST.get('wallet_bep20', '').strip()
            platform_settings.save()
            messages.success(request, 'تم تحديث عناوين محافظ الإيداع الرسمية بنجاح!')

        elif action == 'resolve_tx':
            with transaction.atomic():
                tx = Transaction.objects.select_for_update().filter(
                    id=request.POST.get('tx_id'),
                    status='قيد المراجعة'
                ).first()
                if tx:
                    decision = request.POST.get('decision')
                    locked_user = User.objects.select_for_update().get(pk=tx.user_id)
                    if decision == 'approve':
                        tx.status = 'مكتمل'
                        if tx.tx_type == 'إيداع':
                            locked_user.real_balance += tx.amount
                            locked_user.total_deposited += tx.amount
                            locked_user.save(update_fields=['real_balance', 'total_deposited'])
                        tx.save(update_fields=['status'])
                        messages.success(request, f'تم قبول {tx.tx_type} بقيمة ${tx.amount}!')
                    elif decision == 'reject':
                        tx.status = 'مرفوض'
                        if tx.tx_type == 'سحب':
                            locked_user.real_balance += tx.amount
                            locked_user.save(update_fields=['real_balance'])
                        tx.save(update_fields=['status'])
                        messages.error(request, f'تم رفض عملية {tx.tx_type}.')

        elif action == 'save_risk':
            u = User.objects.filter(id=request.POST.get('user_id')).first()
            if u:
                if request.POST.get('sub_action') == 'reset_daily':
                    u.daily_profit = Decimal('0.00')
                    u.save(update_fields=['daily_profit'])
                    messages.success(request, f'تم تصفير عداد ربح اليوم للمتداول #{u.id}.')
                else:
                    u.cap_type = request.POST.get('cap_type', 'fixed')
                    u.profit_cap = Decimal(request.POST.get('profit_cap', '20') or '20')
                    u.risk_mode = request.POST.get('risk_mode', 'capped')
                    u.save(update_fields=['cap_type', 'profit_cap', 'risk_mode'])
                    messages.success(request, f'تم تحديث إعدادات سقف الربح للمتداول #{u.id}!')

        elif action == 'add_asset':
            sym = request.POST.get('symbol', '').strip().upper()
            name = request.POST.get('name', '').strip()
            if sym and name:
                Asset.objects.update_or_create(
                    symbol=sym,
                    defaults={
                        'name': name,
                        'category': request.POST.get('category', 'فوركس'),
                        'payout': int(request.POST.get('payout', 90) or 90),
                        'min_deposit': Decimal(request.POST.get('min_deposit', '100') or '100'),
                    }
                )
                messages.success(request, f'تمت إضافة/تحديث الزوج {sym} بنجاح!')

        elif action in ('update_asset', 'toggle_lock_asset', 'delete_asset'):
            asset = Asset.objects.filter(id=request.POST.get('asset_id')).first()
            if asset:
                if action == 'delete_asset':
                    asset.delete()
                    messages.error(request, f'تم حذف الزوج {asset.symbol}.')
                elif action == 'toggle_lock_asset':
                    asset.locked_by_admin = not asset.locked_by_admin
                    asset.save(update_fields=['locked_by_admin'])
                    messages.success(request, f'تم تغيير حالة قفل الزوج {asset.symbol}.')
                elif action == 'update_asset':
                    asset.min_deposit = Decimal(request.POST.get('min_deposit', '0') or '0')
                    asset.payout = int(request.POST.get('payout', 85) or 85)
                    asset.save(update_fields=['min_deposit', 'payout'])
                    messages.success(request, f'تم حفظ إعدادات الزوج {asset.symbol}.')

        return redirect('admin_panel')

    context = {
        'platform_settings': platform_settings,
        'unused_codes': ActivationCode.objects.filter(is_used=False),
        'used_codes': ActivationCode.objects.filter(is_used=True).select_related('used_by')[:50],
        'traders': User.objects.filter(is_superuser=False).order_by('-id'),
        'kyc_list': KYCDocument.objects.select_related('user').order_by('-submitted_at'),
        'transactions': Transaction.objects.select_related('user').all()[:100],
        'assets': Asset.objects.all(),
        'trades': Trade.objects.select_related('user').all()[:100],
    }
    return render(request, 'admin.html', context)
