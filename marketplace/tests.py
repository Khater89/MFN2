import tempfile
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from .models import Profile, Service, Slot, Product, Transaction, Notification, MarketplacePolicy, OrderItem, SavedAddress, Issue
from .views import quote_token

class MarketplaceTests(TestCase):
    def setUp(self):
        self.patient=User.objects.create_user('patient',email='patient@example.test',password='ExampleStrongPass99!')
        self.other=User.objects.create_user('other',password='ExampleStrongPass99!')
        self.doctor=User.objects.create_user('doctor',password='ExampleStrongPass99!')
        self.pharmacist=User.objects.create_user('pharmacy',password='ExampleStrongPass99!')
        self.admin=User.objects.create_user('admin',password='ExampleStrongPass99!',is_staff=True)
        Profile.objects.create(user=self.patient,display_name='Patient',role='patient',city='Amman')
        Profile.objects.create(user=self.other,display_name='Other',role='patient',city='Irbid')
        self.provider=Profile.objects.create(user=self.doctor,display_name='Doctor',role='doctor',verification='approved',service_areas='Amman, Zarqa')
        self.pharmacy=Profile.objects.create(user=self.pharmacist,display_name='Pharmacy',role='pharmacy',verification='approved',service_areas='Amman')
        self.service=Service.objects.create(provider=self.provider,title='Home care',category='home',description='Home visit',price=Decimal('35.125'))
        self.slot=Slot.objects.create(service=self.service,starts_at=timezone.now()+timedelta(days=1))
        self.product=Product.objects.create(pharmacy=self.pharmacy,name='First aid kit',category='Essentials',description='Kit',price=Decimal('14.750'),stock=3)
    def data(self,**updates):
        data={'city':'Amman','address':'10 Test Street, building 4','quantity':1,'slot':self.slot.pk,'acknowledge':'on','quote':quote_token(self.patient,[{'kind':'booking','id':self.service.pk,'price':'35.125','currency':'JOD'}])};data.update(updates);return data
    def book(self):
        self.client.force_login(self.patient)
        return self.client.post(f'/checkout/booking/{self.service.pk}/',self.data())
    def order(self,quantity=1):
        self.client.force_login(self.patient)
        return self.client.post(f'/checkout/order/{self.product.pk}/',self.data(quantity=quantity,quote=quote_token(self.patient,[{'kind':'order','id':self.product.pk,'price':'14.750','currency':'JOD'}])))
    def test_marketplace_filters_and_no_results(self):
        self.assertContains(self.client.get('/'),'Home care')
        self.assertNotContains(self.client.get('/?city=Irbid'),'Home care')
        self.assertContains(self.client.get('/?q=nonexistent'),'No care matches yet')
        self.assertNotContains(self.client.get('/?category=pharmacy'),'Home care')
        self.provider.verification='pending';self.provider.save()
        self.assertNotContains(self.client.get('/'),'Home care')
        self.assertEqual(self.client.get(f'/providers/{self.provider.pk}/').status_code,404)
    def test_public_and_protected_templates_render(self):
        for url in ['/','/register/','/login/',f'/providers/{self.provider.pk}/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        for user in [self.patient,self.doctor,self.pharmacist]:
            self.client.force_login(user);self.assertEqual(self.client.get('/dashboard/').status_code,200)
        self.client.force_login(self.doctor)
        for url in ['/onboarding/','/services/new/',f'/services/{self.service.pk}/availability/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.client.force_login(self.pharmacist)
        self.assertEqual(self.client.get('/catalog/new/').status_code,200)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/operations/').status_code,200)
    def test_book_persists_jod_precision_and_unpaid_status(self):
        response=self.book();self.assertEqual(response.status_code,302)
        t=Transaction.objects.get();self.assertEqual(t.total,Decimal('35.125'));self.assertEqual(t.currency,'JOD');self.assertEqual(t.payment_status,'unpaid');self.assertEqual(t.status,'requested');self.assertEqual(t.commission_amount,0)
        self.assertEqual(t.history.count(),1);self.assertEqual(Notification.objects.count(),2)
        self.assertContains(self.client.get(response.url),'Payment')
    def test_duplicate_slot_and_overlap_rejected(self):
        self.book()
        self.assertEqual(self.client.post(f'/checkout/booking/{self.service.pk}/',self.data()).status_code,200)
        second=Service.objects.create(provider=self.provider,title='Second service',category='home',description='Visit',price=20,duration=30)
        slot=Slot.objects.create(service=second,starts_at=self.slot.starts_at+timedelta(minutes=15))
        response=self.client.post(f'/checkout/booking/{second.pk}/',self.data(slot=slot.pk,quote=quote_token(self.patient,[{'kind':'booking','id':second.pk,'price':'20.000','currency':'JOD'}])))
        self.assertContains(response,'overlapping appointment');self.assertEqual(Transaction.objects.count(),1)
    def test_validation_preserves_address_and_blocks_wrong_area(self):
        self.client.force_login(self.patient)
        response=self.client.post(f'/checkout/booking/{self.service.pk}/',self.data(city='Irbid'))
        self.assertContains(response,'does not serve this city');self.assertContains(response,'10 Test Street');self.assertEqual(Transaction.objects.count(),0)
        response=self.client.post(f'/checkout/booking/{self.service.pk}/',self.data(address='x'))
        self.assertContains(response,'Enter a complete address')
        response=self.client.post(f'/checkout/booking/{self.service.pk}/',self.data(acknowledge=''))
        self.assertContains(response,'This field is required');self.assertEqual(Transaction.objects.count(),0)
    def test_inventory_reservation_and_cancellation_are_once_only(self):
        self.order(2);t=Transaction.objects.get();self.product.refresh_from_db();self.assertEqual(self.product.stock,1);self.assertEqual(t.total,Decimal('29.500'))
        response=self.order(2);self.assertContains(response,'Not enough stock');self.assertEqual(Transaction.objects.count(),1)
        self.assertEqual(self.client.post(f'/requests/{t.pk}/status/',{'status':'cancelled'}).status_code,302)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,3)
        self.assertEqual(self.client.post(f'/requests/{t.pk}/status/',{'status':'cancelled'}).status_code,403)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,3)
    def test_patient_cancellation_releases_slot(self):
        self.book();t=Transaction.objects.get();self.client.post(f'/requests/{t.pk}/status/',{'status':'cancelled'})
        t.refresh_from_db();self.assertIsNone(t.slot_id);self.assertIsNotNone(t.scheduled_at)
        self.assertEqual(self.client.post(f'/checkout/booking/{self.service.pk}/',self.data()).status_code,302)
    def test_roles_ownership_and_transition_guards(self):
        self.book();t=Transaction.objects.get()
        self.assertEqual(self.client.get('/operations/').status_code,403)
        self.assertEqual(self.client.get('/catalog/new/').status_code,403)
        self.assertEqual(self.client.post(f'/requests/{t.pk}/status/',{'status':'completed'}).status_code,403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/requests/{t.pk}/').status_code,403)
        self.assertEqual(self.client.post(f'/requests/{t.pk}/status/',{'status':'cancelled'}).status_code,403)
        self.client.force_login(self.doctor)
        self.assertEqual(self.client.get('/operations/').status_code,403)
        self.assertEqual(self.client.get(f'/checkout/booking/{self.service.pk}/').status_code,403)
        self.assertEqual(self.client.post(f'/requests/{t.pk}/status/',{'status':'accepted'}).status_code,302)
        self.assertEqual(self.client.post(f'/requests/{t.pk}/status/',{'status':'completed'}).status_code,302)
        t.refresh_from_db();self.assertEqual(t.status,'completed');self.assertEqual(t.payment_status,'unpaid')
    def test_missing_gateway_never_claims_payment(self):
        self.book();t=Transaction.objects.get()
        response=self.client.post(f'/requests/{t.pk}/payment/')
        self.assertEqual(response.status_code,503);t.refresh_from_db();self.assertEqual(t.payment_status,'unpaid');self.assertEqual(t.commission_amount,0)
    def test_upload_validation_privacy_and_review(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.client.force_login(self.doctor)
            data={'display_name':'Doctor','city':'Amman','service_areas':'Amman','license_number':'LICENSE-1','revision':0}
            response=self.client.post('/onboarding/',{**data,'license_document':SimpleUploadedFile('bad.pdf',b'not a pdf')})
            self.assertContains(response,'does not match its extension')
            response=self.client.post('/onboarding/',{**data,'license_document':SimpleUploadedFile('license.pdf',b'%PDF-1.7\nSample test file')})
            self.assertEqual(response.status_code,302);self.provider.refresh_from_db();self.assertEqual(self.provider.verification,'pending')
            self.client.force_login(self.patient);self.assertEqual(self.client.get(f'/licenses/{self.provider.pk}/').status_code,403)
            self.client.force_login(self.admin)
            self.assertEqual(self.client.get(f'/licenses/{self.provider.pk}/').status_code,200)
            response=self.client.post(f'/operations/review/{self.provider.pk}/',{'decision':'approved','notes':'Credentials independently checked in test'})
            self.assertEqual(response.status_code,302);self.provider.refresh_from_db();self.assertEqual(self.provider.verification,'approved')
            self.assertEqual(self.client.post(f'/operations/review/{self.provider.pk}/',{'decision':'rejected','notes':'stale review'}).status_code,409)
    def test_product_edit_conflict_and_ownership(self):
        self.client.force_login(self.pharmacist)
        data={'name':'Kit','category':'Essentials','description':'Test','price':'14.750','currency':'JOD','stock':4,'active':'on','revision':0}
        self.product.revision=1;self.product.save()
        self.assertContains(self.client.post(f'/catalog/{self.product.pk}/',data),'This product changed')
        self.product.refresh_from_db();self.assertEqual(self.product.stock,3)
        self.client.force_login(self.doctor);self.assertEqual(self.client.get(f'/catalog/{self.product.pk}/').status_code,403)
    def test_commission_policy_is_admin_only_and_snapshotted(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post('/operations/',{'commission_percent':'12.5','currency':'JOD','revision':0,'confirm':'on'}).status_code,302)
        self.book();t=Transaction.objects.get();self.assertEqual(t.commission_rate,Decimal('12.50'));self.assertEqual(t.commission_amount,0)
        self.assertEqual(self.client.post('/operations/',{'commission_percent':100,'currency':'JOD','revision':1,'confirm':'on'}).status_code,403)
    def test_registration_role_cannot_escalate_to_admin(self):
        response=self.client.post('/register/',{'username':'new-user','full_name':'New patient','email':'new@example.test','role':'admin','city':'Amman','password1':'ExampleStrongPass99!','password2':'ExampleStrongPass99!'})
        self.assertEqual(response.status_code,200);self.assertFalse(User.objects.filter(username='new-user').exists())
        response=self.client.post('/register/',{'username':'new-user','full_name':'New patient','email':'new@example.test','role':'patient','city':'Amman','password1':'ExampleStrongPass99!','password2':'ExampleStrongPass99!'})
        self.assertEqual(response.status_code,302);self.assertFalse(User.objects.get(username='new-user').is_staff)
    def test_cart_multiple_items_total_and_restoration(self):
        second=Product.objects.create(pharmacy=self.pharmacy,name='Thermometer',category='Monitoring',description='Sample',price=Decimal('8.500'),stock=5)
        self.client.force_login(self.patient)
        self.client.post(f'/cart/add/{self.product.pk}/');self.client.post(f'/cart/add/{second.pk}/')
        self.assertContains(self.client.get('/cart/'),'23.250')
        response=self.client.get('/cart/checkout/');quote=response.context['form'].initial['quote']
        response=self.client.post('/cart/checkout/',self.data(quote=quote));self.assertEqual(response.status_code,302)
        t=Transaction.objects.get();self.assertEqual(t.items.count(),2);self.assertEqual(t.total,Decimal('23.250'))
        self.product.refresh_from_db();second.refresh_from_db();self.assertEqual(self.product.stock,2);self.assertEqual(second.stock,4)
        self.assertEqual(self.client.session['cart'],{})
        self.client.post(f'/requests/{t.pk}/status/',{'status':'cancelled'})
        self.product.refresh_from_db();second.refresh_from_db();self.assertEqual(self.product.stock,3);self.assertEqual(second.stock,5)
    def test_cart_rejects_second_pharmacy_and_stock_changes(self):
        foreign=Product.objects.create(pharmacy=self.provider,name='Other merchant',category='Test',description='Test',price=1,stock=10)
        self.client.force_login(self.patient);self.client.post(f'/cart/add/{self.product.pk}/')
        self.client.post(f'/cart/add/{foreign.pk}/');self.assertNotIn(str(foreign.pk),self.client.session['cart'])
        response=self.client.get('/cart/checkout/');quote=response.context['form'].initial['quote']
        self.product.stock=0;self.product.save()
        response=self.client.post('/cart/checkout/',self.data(quote=quote));self.assertContains(response,'Stock or availability changed');self.assertEqual(Transaction.objects.count(),0)
    def test_stale_prices_and_tampered_quotes_are_rejected(self):
        self.client.force_login(self.patient)
        data=self.data();self.service.price=Decimal('40.000');self.service.save()
        self.assertContains(self.client.post(f'/checkout/booking/{self.service.pk}/',data),'quote expired or the price changed');self.assertEqual(Transaction.objects.count(),0)
        self.assertContains(self.client.post(f'/checkout/booking/{self.service.pk}/',self.data(quote='tampered')),'quote expired or the price changed')
    def test_saved_addresses_are_private(self):
        self.client.force_login(self.patient)
        self.assertEqual(self.client.post('/account/',{'label':'Home','city':'Amman','address':'123 Patient Street'}).status_code,302)
        address=SavedAddress.objects.get()
        self.client.post(f'/account/addresses/{address.pk}/',{'action':'default'})
        self.patient.profile.refresh_from_db();self.assertEqual(self.patient.profile.address,'123 Patient Street')
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(f'/account/addresses/{address.pk}/',{'action':'delete'}).status_code,404)
        self.assertNotContains(self.client.get('/account/'),'123 Patient Street')
    def test_issue_submission_resolution_and_roles(self):
        self.book();t=Transaction.objects.get()
        self.assertEqual(self.client.post(f'/requests/{t.pk}/issue/',{'description':'I need help coordinating this appointment.'}).status_code,302)
        issue=Issue.objects.get();self.assertEqual(issue.status,'open')
        self.assertEqual(self.client.post(f'/operations/issues/{issue.pk}/resolve/',{'resolution':'Patient cannot resolve an issue.'}).status_code,403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/operations/'),'coordinating this appointment')
        self.assertEqual(self.client.post(f'/operations/issues/{issue.pk}/resolve/',{'resolution':'Coordinated appointment with both parties.'}).status_code,302)
        issue.refresh_from_db();self.assertEqual(issue.status,'resolved')
        self.assertEqual(self.client.post(f'/operations/issues/{issue.pk}/resolve/',{'resolution':'Repeated resolution should fail.'}).status_code,409)
        t.refresh_from_db();self.assertEqual(t.payment_status,'unpaid')
    def test_service_edit_conflicts_and_reserved_slot_removal(self):
        self.book();self.client.force_login(self.doctor)
        response=self.client.post(f'/availability/{self.slot.pk}/remove/')
        self.assertEqual(response.status_code,302);self.assertTrue(Slot.objects.filter(pk=self.slot.pk).exists())
        data={'title':'Home care','category':'home','description':'Visit','price':'35.125','currency':'JOD','duration':90,'active':'on','revision':0}
        self.assertContains(self.client.post(f'/services/{self.service.pk}/edit/',data),'Resolve active requests')
        self.service.refresh_from_db();self.assertEqual(self.service.duration,45)
