"""Exercise competing HTTP submissions against an isolated SQLite file."""
import os
import sys
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
with tempfile.TemporaryDirectory(prefix='medical-concurrency-') as directory:
    os.environ['DATABASE_PATH'] = str(Path(directory) / 'test.sqlite3')
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth.models import User
    from django.test import Client
    from django.utils import timezone
    from django.db import connections
    from marketplace.models import Profile, Service, Slot, Product, Transaction
    from marketplace.views import quote_token

    call_command('migrate', verbosity=0)
    patient = User.objects.create_user('race-patient')
    Profile.objects.create(user=patient, display_name='Test patient', role='patient')
    doctor = User.objects.create_user('race-doctor')
    provider = Profile.objects.create(user=doctor, display_name='Test provider', role='doctor', verification='approved', service_areas='Amman')
    service = Service.objects.create(provider=provider, title='Race visit', category='home', description='Test', price='35.125')
    slot = Slot.objects.create(service=service, starts_at=timezone.now() + timedelta(days=1))
    pharmacist = User.objects.create_user('race-pharmacy')
    pharmacy = Profile.objects.create(user=pharmacist, display_name='Test pharmacy', role='pharmacy', verification='approved', service_areas='Amman')
    product = Product.objects.create(pharmacy=pharmacy, name='Last item', category='Test', description='Test', price='8.500', stock=1)

    def compete(kind, item, price):
        barrier = Barrier(2)
        data = {'city':'Amman', 'address':'12 Race Test Street', 'quantity':1, 'acknowledge':'on', 'slot':slot.pk,
                'quote':quote_token(patient, [{'kind':kind, 'id':item.pk, 'price':price, 'currency':'JOD'}])}
        def submit(_):
            client = Client()
            client.force_login(User.objects.get(pk=patient.pk))
            barrier.wait(timeout=10)
            try:
                return client.post(f'/checkout/{kind}/{item.pk}/', data).status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = sorted(executor.map(submit, range(2)))
        assert statuses == [200,302], f'{kind}: expected one reservation, got {statuses}'
        assert Transaction.objects.filter(kind=kind).count() == 1
        print(f'{kind}: two concurrent submissions, exactly one reservation; passed')

    compete('booking', service, '35.125')
    compete('order', product, '8.500')
    product.refresh_from_db()
    assert product.stock == 0
    connections.close_all()
