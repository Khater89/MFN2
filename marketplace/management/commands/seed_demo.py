from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from marketplace.models import Profile, Service, Product, Slot, MarketplacePolicy

class Command(BaseCommand):
    help = 'Create clearly marked sample Jordan marketplace listings. Does not create usable demo login passwords.'
    def handle(self, *args, **options):
        samples = [
            ('demo-doctor','Dr. Lina Haddad','doctor','Family medicine','Amman, Zarqa','A sample family doctor profile for exploring home care. This is not a real clinician.'),
            ('demo-nurse','Nurse Omar Khalil','nurse','Community nursing','Amman, Irbid','A sample nursing profile demonstrating the provider marketplace. No real care is offered.'),
            ('demo-specialist','Dr. Rania Mansour','doctor','Internal medicine','Amman','A sample physician profile for consultation request testing.'),
            ('demo-pharmacy','Olive Care Pharmacy','pharmacy','Health essentials','Amman, Zarqa, Irbid','Sample pharmacy catalog. Products are fictional inventory for development only.')
        ]
        profiles={}
        for username,name,role,specialty,areas,bio in samples:
            user,created=User.objects.get_or_create(username=username,defaults={'first_name':name})
            if created: user.set_unusable_password();user.save()
            profile,created=Profile.objects.get_or_create(user=user,defaults={'display_name':name,'role':role,'specialty':specialty,'city':'Amman','service_areas':areas,'bio':bio,'verification':'approved','demo':True})
            if not profile.demo: raise RuntimeError('Refusing to overwrite a non-demo profile.')
            profiles[username]=profile
        for username,title,category,price,duration,description in [
            ('demo-doctor','Doctor home visit','home','35.000',45,'A general health consultation in the comfort of your home.'),
            ('demo-nurse','Home nursing visit','home','25.000',60,'Request a qualified nursing visit for routine care and support.'),
            ('demo-specialist','Specialist consultation','consultation','30.000',30,'Request an appointment to discuss your health with a specialist.')
        ]:
            service,_=Service.objects.get_or_create(provider=profiles[username],title=title,defaults={'category':category,'price':Decimal(price),'duration':duration,'description':description})
            for day in range(1,8):
                for hour in [9,11,14,16]:
                    starts=(timezone.localtime()+timedelta(days=day)).replace(hour=hour,minute=0,second=0,microsecond=0)
                    Slot.objects.get_or_create(service=service,starts_at=starts)
        for name,category,price,stock,description in [
            ('Digital thermometer','Home monitoring','8.500',24,'A sample digital thermometer for everyday home monitoring.'),
            ('Home first aid kit','Everyday essentials','14.750',18,'A sample basic first aid kit. No prescription items are listed.'),
            ('Blood pressure monitor','Home monitoring','39.900',12,'A sample home blood pressure monitor for catalog testing.')
        ]:
            Product.objects.get_or_create(pharmacy=profiles['demo-pharmacy'],name=name,defaults={'category':category,'price':Decimal(price),'stock':stock,'description':description})
        MarketplacePolicy.objects.get_or_create(pk=1,defaults={'currency':'JOD'})
        self.stdout.write(self.style.SUCCESS('Demo Jordan listings ready. No patient accounts or payment credentials created.'))
