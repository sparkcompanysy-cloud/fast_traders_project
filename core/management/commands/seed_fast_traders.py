from decimal import Decimal
from django.core.management.base import BaseCommand
from core.models import Asset, PlatformSetting


class Command(BaseCommand):
    help = 'Seeds default trading assets and platform wallet settings'

    def handle(self, *args, **options):
        # 1. Ensure Platform Settings exist
        PlatformSetting.get_solo()
        self.stdout.write(self.style.SUCCESS('✓ Platform wallet settings initialized.'))

        # 2. Seed Default Assets
        default_assets = [
            {
                'symbol': 'EUR/USD',
                'name': 'يورو / دولار أمريكي',
                'category': 'فوركس',
                'payout': 92,
                'min_deposit': Decimal('200.00'),
                'base_price': Decimal('1.08450'),
            },
            {
                'symbol': 'CAD/USD',
                'name': 'دولار كندي / دولار',
                'category': 'فوركس',
                'payout': 88,
                'min_deposit': Decimal('1000.00'),
                'base_price': Decimal('0.73120'),
            },
            {
                'symbol': 'BTC/USDT',
                'name': 'بتكوين / تيثير',
                'category': 'عملات رقمية',
                'payout': 90,
                'min_deposit': Decimal('100.00'),
                'base_price': Decimal('67432.80000'),
            },
            {
                'symbol': 'GOLD',
                'name': 'عقود الذهب الفورية',
                'category': 'معادن',
                'payout': 86,
                'min_deposit': Decimal('500.00'),
                'base_price': Decimal('2345.50000'),
            },
        ]

        for item in default_assets:
            Asset.objects.get_or_create(symbol=item['symbol'], defaults=item)
        self.stdout.write(self.style.SUCCESS('✓ Default trading pairs (EUR/USD, CAD/USD, BTC/USDT, GOLD) seeded.'))
