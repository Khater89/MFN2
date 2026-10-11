from django.contrib import admin
from .models import Profile, Service, Slot, Product, Transaction, Activity, Notification, MarketplacePolicy
for model in [Profile, Service, Slot, Product, Transaction, Activity, Notification, MarketplacePolicy]:
    admin.site.register(model)
