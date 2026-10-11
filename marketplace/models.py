import uuid
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

def license_path(instance, filename):
    return f'licenses/{instance.user_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'

class Profile(models.Model):
    ROLES = [('patient','Patient'), ('doctor','Doctor'), ('nurse','Nurse'), ('pharmacy','Pharmacy')]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=ROLES, default='patient')
    display_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=80, blank=True)
    address = models.CharField(max_length=250, blank=True)
    specialty = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    service_areas = models.CharField(max_length=300, blank=True, help_text='Comma-separated city names')
    license_number = models.CharField(max_length=80, blank=True)
    license_document = models.FileField(upload_to=license_path, blank=True)
    verification = models.CharField(max_length=12, choices=[('pending','Pending review'), ('approved','Approved'), ('rejected','Rejected')], default='pending')
    review_notes = models.TextField(blank=True)
    demo = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.display_name
    def serves(self, city): return city.strip().casefold() in [x.strip().casefold() for x in self.service_areas.split(',')]

class Service(models.Model):
    provider = models.ForeignKey(Profile, on_delete=models.CASCADE)
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=[('home','Home visit'), ('consultation','Consultation request')])
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    currency = models.CharField(max_length=3, default='JOD')
    duration = models.PositiveIntegerField(default=45, validators=[MinValueValidator(15), MaxValueValidator(240)])
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=0)
    def __str__(self): return self.title

class Slot(models.Model):
    service = models.ForeignKey(Service, related_name='slots', on_delete=models.CASCADE)
    starts_at = models.DateTimeField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['service','starts_at'], name='unique_service_slot')]
        ordering = ['starts_at']

class Product(models.Model):
    pharmacy = models.ForeignKey(Profile, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=60)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    currency = models.CharField(max_length=3, default='JOD')
    stock = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=0)
    def __str__(self): return self.name

class MarketplacePolicy(models.Model):
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    currency = models.CharField(max_length=3, blank=True)
    revision = models.PositiveIntegerField(default=0)
    @classmethod
    def current(cls): return cls.objects.get_or_create(pk=1)[0]

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='requests', on_delete=models.PROTECT)
    merchant = models.ForeignKey(Profile, on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, choices=[('booking','Booking'), ('order','Order')])
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.PROTECT)
    slot = models.OneToOneField(Slot, null=True, blank=True, on_delete=models.PROTECT)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    address = models.CharField(max_length=250)
    status = models.CharField(max_length=20, default='requested', choices=[('requested','Requested'), ('accepted','Accepted'), ('completed','Completed'), ('cancelled','Cancelled')])
    payment_status = models.CharField(max_length=20, default='unpaid')
    subtotal = models.DecimalField(max_digits=11, decimal_places=3)
    total = models.DecimalField(max_digits=11, decimal_places=3)
    currency = models.CharField(max_length=3)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    commission_amount = models.DecimalField(max_digits=11, decimal_places=3, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Activity(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    transaction = models.ForeignKey(Transaction, null=True, blank=True, related_name='history', on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    outcome = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']

class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: ordering = ['-created_at']

class OrderItem(models.Model):
    transaction = models.ForeignKey(Transaction, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=3)

class SavedAddress(models.Model):
    patient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    label = models.CharField(max_length=50)
    city = models.CharField(max_length=80)
    address = models.CharField(max_length=250)

class Issue(models.Model):
    transaction = models.ForeignKey(Transaction, related_name='issues', on_delete=models.PROTECT)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    description = models.TextField()
    status = models.CharField(max_length=12, default='open', choices=[('open','Open'),('resolved','Resolved')])
    resolution = models.TextField(blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='resolved_issues', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
