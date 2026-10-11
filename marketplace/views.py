from datetime import timedelta
from decimal import Decimal
from functools import wraps
from pathlib import Path
from django import forms
from django.core import signing
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction as db_transaction
from django.db.models import F, Q, Sum
from django.http import HttpResponseForbidden, FileResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from .models import Profile, Product, Service, Slot, Transaction, Activity, Notification, MarketplacePolicy, OrderItem, SavedAddress, Issue
from .forms import RegistrationForm, OnboardingForm, CheckoutForm, ProductForm, ServiceForm, PolicyForm

def role_required(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if 'admin' in roles and request.user.is_staff: return view(request, *args, **kwargs)
            if getattr(getattr(request.user,'profile',None),'role',None) not in roles: return HttpResponseForbidden('This action is not available for your role.')
            return view(request, *args, **kwargs)
        return wrapped
    return decorator

def event(actor, action, outcome, record=None, recipients=()):
    Activity.objects.create(actor=actor, action=action, outcome=outcome, transaction=record)
    for recipient in set(recipients): Notification.objects.create(recipient=recipient, text=f'{action}: {outcome}')

def quote_token(user, rows):
    return signing.dumps({'user':user.pk,'rows':rows},salt='checkout-quote')

def valid_quote(token,user,rows):
    try: return signing.loads(token,salt='checkout-quote',max_age=900)=={'user':user.pk,'rows':rows}
    except signing.BadSignature: return False

def home(request):
    q = request.GET.get('q','').strip()[:100]
    city = request.GET.get('city','').strip()[:80]
    category = request.GET.get('category','all')
    providers = Profile.objects.filter(verification='approved', user__is_active=True).exclude(role='patient')
    services = Service.objects.filter(active=True, provider__in=providers).select_related('provider')
    products = Product.objects.filter(active=True, pharmacy__in=providers).select_related('pharmacy')
    if q:
        services = services.filter(Q(title__icontains=q)|Q(provider__display_name__icontains=q)|Q(provider__specialty__icontains=q))
        products = products.filter(Q(name__icontains=q)|Q(category__icontains=q)|Q(pharmacy__display_name__icontains=q))
    services = list(services)
    products = list(products)
    if city:
        services = [s for s in services if s.provider.serves(city)]
        products = [p for p in products if p.pharmacy.serves(city)]
    if category == 'pharmacy': services = []
    elif category in ['doctor','nurse']: services = [s for s in services if s.provider.role == category]; products = []
    elif category == 'home': services = [s for s in services if s.category == 'home']; products = []
    return render(request,'marketplace/home.html',{'services':services, 'products':products, 'q':q, 'city':city, 'category':category, 'result_count':len(services)+len(products), 'cities':sorted({a.strip() for p in providers for a in p.service_areas.split(',') if a.strip()})})

def profile(request, pk):
    provider = get_object_or_404(Profile, pk=pk, verification='approved', user__is_active=True)
    if provider.role == 'patient': return HttpResponseForbidden()
    return render(request,'marketplace/profile.html',{'provider':provider,'services':provider.service_set.filter(active=True), 'products':provider.product_set.filter(active=True)})

def register(request):
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with db_transaction.atomic():
            user = form.save(commit=False); user.email = form.cleaned_data['email']; user.first_name = form.cleaned_data['full_name']; user.save()
            p = Profile.objects.create(user=user, display_name=form.cleaned_data['full_name'], role=form.cleaned_data['role'], city=form.cleaned_data['city'])
            event(user, 'Account created', 'Onboarding available', recipients=[user])
        login(request,user)
        return redirect('dashboard' if p.role == 'patient' else 'onboarding')
    return render(request,'marketplace/form.html',{'form':form,'title':'Your care journey starts here','eyebrow':'CREATE ACCOUNT','description':'Choose your role. Medical providers and pharmacies must complete private license review before receiving requests.','button':'Create account'})

@role_required('doctor','nurse','pharmacy')
def onboarding(request):
    p = Profile.objects.get(user=request.user)
    revision = p.revision
    form = OnboardingForm(request.POST or None, request.FILES or None, instance=p, initial={'revision':revision})
    if request.method == 'POST' and form.is_valid():
        with db_transaction.atomic():
            if not Profile.objects.filter(pk=p.pk, revision=form.cleaned_data['revision']).update(revision=F('revision')+1):
                form.add_error(None,'Your profile changed in another session. Reload before submitting.')
            else:
                updated = form.save(commit=False); updated.revision = revision+1; updated.verification='pending'; updated.review_notes=''; updated.save()
                event(request.user,'License submitted','Pending admin review',recipients=list(User.objects.filter(is_staff=True))+[request.user])
                messages.success(request,'Your documents were saved privately. Approval is pending.'); return redirect('dashboard')
    return render(request,'marketplace/form.html',{'form':form,'title':'Complete your provider profile','eyebrow':'PRIVATE LICENSE REVIEW','description':'PDF, PNG or JPEG · maximum 5 MB. Documents are available only to you and administrators. Editing an approved profile requires a new review.','button':'Submit for review','upload':True})

@role_required('patient')
def checkout(request, kind, pk):
    if kind == 'booking': item = get_object_or_404(Service,pk=pk,active=True,provider__verification='approved',provider__user__is_active=True); merchant=item.provider
    elif kind == 'order': item=get_object_or_404(Product,pk=pk,active=True,pharmacy__verification='approved',pharmacy__user__is_active=True); merchant=item.pharmacy
    else: return HttpResponseForbidden()
    p = request.user.profile
    quote_rows=[{'kind':kind,'id':item.pk,'price':str(item.price),'currency':item.currency}]
    form = CheckoutForm(request.POST or None,initial={'city':p.city,'address':p.address,'quote':quote_token(request.user,quote_rows)})
    slots = Slot.objects.filter(service=item,starts_at__gt=timezone.now(),transaction__isnull=True) if kind == 'booking' else Slot.objects.none()
    form.fields['slot'].choices=[('', 'Choose an available appointment')]+[(str(s.pk),timezone.localtime(s.starts_at).strftime('%a, %d %b · %H:%M')+f' ({settings.TIME_ZONE})') for s in slots]
    if kind == 'booking': form.fields['slot'].required=True; form.fields['quantity'].widget=forms.HiddenInput()
    else: del form.fields['slot']
    if request.method == 'POST' and form.is_valid():
        with db_transaction.atomic():
            # First write serializes competing reservations in SQLite; PostgreSQL can use a row lock.
            Profile.objects.filter(pk=merchant.pk).update(revision=F('revision')+1)
            merchant.refresh_from_db(); item.refresh_from_db()
            current_rows=[{'kind':kind,'id':item.pk,'price':str(item.price),'currency':item.currency}]
            if not valid_quote(form.cleaned_data['quote'],request.user,current_rows): form.add_error(None,'This quote expired or the price changed. Reload checkout to review the current price.')
            elif merchant.verification != 'approved' or not item.active: form.add_error(None,'This listing is no longer available.')
            elif not merchant.serves(form.cleaned_data['city']): form.add_error('city','This provider does not serve this city. Choose one of: '+merchant.service_areas)
            else:
                slot = None
                if kind == 'booking':
                    slot = Slot.objects.filter(pk=form.cleaned_data['slot'],service=item, starts_at__gt=timezone.now(),transaction__isnull=True).first()
                    if not slot: form.add_error('slot','This time was just reserved. Choose another appointment.')
                    else:
                        end = slot.starts_at + timedelta(minutes=item.duration)
                        existing = Transaction.objects.filter(merchant=merchant,kind='booking',status__in=['requested','accepted','completed'],scheduled_at__lt=end).select_related('service')
                        if any(t.scheduled_at+timedelta(minutes=t.service.duration)>slot.starts_at for t in existing): form.add_error('slot','The provider already has an overlapping appointment. Choose another time.')
                elif not Product.objects.filter(pk=item.pk,stock__gte=form.cleaned_data['quantity'],active=True).update(stock=F('stock')-form.cleaned_data['quantity'],revision=F('revision')+1): form.add_error('quantity','Not enough stock remains. Reduce the quantity.')
                if not form.errors:
                    quantity = form.cleaned_data['quantity'] if kind=='order' else 1
                    subtotal = item.price*quantity
                    policy = MarketplacePolicy.current()
                    record = Transaction.objects.create(patient=request.user,merchant=merchant,kind=kind,service=item if kind=='booking' else None,slot=slot,scheduled_at=slot.starts_at if slot else None,product=item if kind=='order' else None,quantity=quantity,title=str(item),city=form.cleaned_data['city'],address=form.cleaned_data['address'],subtotal=subtotal,total=subtotal,currency=item.currency,commission_rate=policy.commission_percent if policy.currency==item.currency else None)
                    if kind=='order': OrderItem.objects.create(transaction=record,product=item,name=item.name,quantity=quantity,unit_price=item.price)
                    event(request.user, 'Request submitted',f'{record.title} · awaiting provider acceptance · unpaid',record,[request.user,merchant.user])
                    Profile.objects.filter(pk=p.pk).update(city=form.cleaned_data['city'],address=form.cleaned_data['address'])
                    return redirect('record',pk=record.pk)
    return render(request,'marketplace/checkout.html',{'form':form,'item':item,'merchant':merchant,'kind':kind})

@login_required
def record(request, pk):
    t=get_object_or_404(Transaction.objects.select_related('merchant','service','patient'),pk=pk)
    if not (request.user.is_staff or request.user.pk in [t.patient_id,t.merchant.user_id]): return HttpResponseForbidden()
    return render(request,'marketplace/record.html',{'record':t,'issue_form':IssueForm()})

@login_required
def dashboard(request):
    if request.user.is_staff: return redirect('operations')
    p=request.user.profile
    records = Transaction.objects.filter(patient=request.user) if p.role=='patient' else Transaction.objects.filter(merchant=p)
    return render(request,'marketplace/dashboard.html',{'records':records.order_by('-created_at'),'notifications':Notification.objects.filter(recipient=request.user)[:15], 'products':Product.objects.filter(pharmacy=p),'services':Service.objects.filter(provider=p),'paid':records.filter(payment_status='paid').aggregate(gross=Sum('subtotal'),commission=Sum('commission_amount'))})

@require_POST
@login_required
def transition(request, pk):
    with db_transaction.atomic():
        # Serialize writes before loading current status.
        Transaction.objects.filter(pk=pk).update(status=F('status'))
        t=get_object_or_404(Transaction.objects.select_related('merchant'),pk=pk)
        target=request.POST.get('status')
        allowed = (request.user.pk==t.merchant.user_id and t.merchant.verification=='approved' and ((t.status=='requested' and target in ['accepted','cancelled']) or (t.status=='accepted' and target=='completed')))
        if request.user.pk==t.patient_id and t.status=='requested' and target=='cancelled': allowed=True
        if not allowed: return HttpResponseForbidden('This status transition is not allowed.')
        t.status=target
        if target=='cancelled':
            t.slot=None
            for item in t.items.all(): Product.objects.filter(pk=item.product_id).update(stock=F('stock')+item.quantity,revision=F('revision')+1)
        t.save()
        event(request.user,'Status updated',t.get_status_display(),t,[t.patient,t.merchant.user])
    return redirect('record',pk=pk)

@role_required('pharmacy')
def product_edit(request, pk=None):
    p=request.user.profile
    if p.verification!='approved': return HttpResponseForbidden('Approval is required to manage catalog listings.')
    item=get_object_or_404(Product,pk=pk,pharmacy=p) if pk else None
    rev=item.revision if item else 0
    form=ProductForm(request.POST or None,instance=item,initial={'revision':rev})
    if request.method=='POST' and form.is_valid():
        with db_transaction.atomic():
            if item and not Product.objects.filter(pk=item.pk,revision=form.cleaned_data['revision']).update(revision=F('revision')+1): form.add_error(None,'This product changed. Reload to avoid overwriting newer stock or edits.')
            else:
                product=form.save(commit=False);product.pharmacy=p;product.revision=rev+1;product.save()
                event(request.user,'Catalog updated',product.name);messages.success(request,'Product saved.');return redirect('dashboard')
    return render(request,'marketplace/form.html',{'form':form,'title':'Edit product' if item else 'Add a medical product','eyebrow':'PHARMACY CATALOG','button':'Save product'})

@role_required('doctor','nurse')
def service_add(request, pk=None):
    p=request.user.profile
    if p.verification!='approved': return HttpResponseForbidden('Approval is required to publish services.')
    item=get_object_or_404(Service,pk=pk,provider=p) if pk else None
    rev=item.revision if item else 0
    form=ServiceForm(request.POST or None,instance=item,initial={'revision':rev})
    if request.method=='POST' and form.is_valid():
        with db_transaction.atomic():
            if item and not Service.objects.filter(pk=item.pk,revision=form.cleaned_data['revision']).update(revision=F('revision')+1): form.add_error(None,'Service changed. Reload before saving.')
            else:
                if item and item.duration != Service.objects.get(pk=item.pk).duration and Transaction.objects.filter(service=item,status__in=['requested','accepted']).exists():
                    form.add_error('duration','Resolve active requests before changing appointment duration.')
                else:
                    service=form.save(commit=False);service.provider=p;service.revision=rev+1;service.save();event(request.user,'Service saved',service.title);return redirect('dashboard')
    return render(request,'marketplace/form.html',{'form':form,'title':'Edit care service' if item else 'Publish a care service','eyebrow':'YOUR SERVICES','button':'Save service'})

@role_required('doctor','nurse')
def slot_add(request, pk):
    service=get_object_or_404(Service,pk=pk,provider__user=request.user,provider__verification='approved')
    class SlotForm(forms.Form):
        starts_at=forms.DateTimeField(label=f'Appointment time ({settings.TIME_ZONE})',widget=forms.DateTimeInput(attrs={'type':'datetime-local'}))
        def clean_starts_at(self):
            dt=self.cleaned_data['starts_at']
            if dt<=timezone.now(): raise forms.ValidationError('Choose a future appointment.')
            if Slot.objects.filter(service=service,starts_at=dt).exists(): raise forms.ValidationError('This slot already exists.')
            return dt
    form=SlotForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        Slot.objects.get_or_create(service=service,starts_at=form.cleaned_data['starts_at']);event(request.user,'Availability added',service.title);return redirect('dashboard')
    return render(request,'marketplace/form.html',{'form':form,'title':'Add appointment availability','description':service.title,'button':'Add appointment'})

@role_required('admin')
def operations(request):
    policy=MarketplacePolicy.current();rev=policy.revision
    form=PolicyForm(request.POST or None,instance=policy,initial={'revision':rev})
    if request.method=='POST' and form.is_valid():
        with db_transaction.atomic():
            if not MarketplacePolicy.objects.filter(pk=1,revision=form.cleaned_data['revision']).update(revision=F('revision')+1): form.add_error(None,'Settings changed. Reload before saving.')
            else:
                policy=form.save(commit=False);policy.revision=rev+1;policy.save();event(request.user,'Commission rule saved',f'{policy.commission_percent}% of gross; {policy.currency}');messages.success(request,'Rule saved for future transactions. No payments or payouts were executed.');return redirect('operations')
    return render(request,'marketplace/operations.html',{'queue':Profile.objects.filter(verification='pending').exclude(role='patient'),'records':Transaction.objects.select_related('patient','merchant').order_by('-created_at')[:50],'activity':Activity.objects.select_related('actor')[:30],'form':form,'issues':Issue.objects.select_related('transaction','opened_by').order_by('-created_at')[:50]})

@require_POST
@role_required('admin')
def review(request, pk):
    with db_transaction.atomic():
        Profile.objects.filter(pk=pk).update(revision=F('revision'))
        p=get_object_or_404(Profile,pk=pk)
        decision=request.POST.get('decision');notes=request.POST.get('notes','').strip()[:500]
        if p.role=='patient' or decision not in ['approved','rejected'] or p.verification!='pending': return JsonResponse({'error':'This review is no longer actionable.'},status=409)
        if decision=='approved' and not (p.license_document and p.license_number and p.service_areas): return JsonResponse({'error':'A license document, license number and service area are required.'},status=400)
        if not notes: return JsonResponse({'error':'Review notes are required.'},status=400)
        p.verification=decision;p.review_notes=notes;p.revision+=1;p.save()
        event(request.user,'License review',f'{p.display_name}: {decision}',recipients=[p.user])
    messages.success(request,'Review recorded.');return redirect('operations')

@login_required
def license_download(request, pk):
    p=get_object_or_404(Profile,pk=pk)
    if not (request.user.is_staff or request.user.pk==p.user_id): return HttpResponseForbidden()
    if not p.license_document: return JsonResponse({'error':'No document uploaded.'},status=404)
    response=FileResponse(p.license_document.open('rb'),as_attachment=True,filename=Path(p.license_document.name).name)
    response['Cache-Control']='private, no-store'
    return response

@require_POST
@role_required('patient')
def payment(request, pk):
    get_object_or_404(Transaction,pk=pk,patient=request.user)
    return JsonResponse({'error':'Live payments are unavailable. A payment gateway and country-specific business policies must be configured. This request remains unpaid.'},status=503)

@require_POST
@role_required('doctor','nurse')
def slot_remove(request, pk):
    with db_transaction.atomic():
        Profile.objects.filter(user=request.user).update(revision=F('revision')+1)
        slot=get_object_or_404(Slot,pk=pk,service__provider__user=request.user)
        if Transaction.objects.filter(slot=slot).exists():
            messages.error(request,'Reserved appointments cannot be removed.')
        else: slot.delete();event(request.user,'Availability removed','Unreserved appointment removed')
    return redirect('dashboard')

@require_POST
@role_required('patient')
def cart_add(request, pk):
    product=get_object_or_404(Product,pk=pk,active=True,pharmacy__verification='approved')
    cart=request.session.get('cart',{})
    existing=Product.objects.filter(pk__in=cart)
    if any(p.pharmacy_id!=product.pharmacy_id or p.currency!=product.currency for p in existing):
        messages.error(request,'Each order is for one pharmacy and currency. Complete or clear your current basket first.')
    elif product.stock <= cart.get(str(pk),0): messages.error(request,'No more stock is available for this item.')
    else: cart[str(pk)]=cart.get(str(pk),0)+1;request.session['cart']=cart;messages.success(request,'Item added to your basket.')
    return redirect('cart')

@role_required('patient')
def cart(request):
    cart_data=request.session.get('cart',{})
    if request.method=='POST':
        if request.POST.get('remove'):
            cart_data.pop(request.POST['remove'],None);request.session['cart']=cart_data;return redirect('cart')
        errors=[]
        for key in cart_data:
            try:
                qty=int(request.POST.get('quantity_'+key,cart_data[key]))
                if not 1<=qty<=50: raise ValueError()
                cart_data[key]=qty
            except (TypeError,ValueError): errors.append('Use quantities between 1 and 50.')
        if errors: messages.error(request,errors[0])
        else: request.session['cart']=cart_data;messages.success(request,'Basket updated.')
    rows=[];total=Decimal('0')
    for product in Product.objects.filter(pk__in=cart_data).select_related('pharmacy'):
        qty=cart_data[str(product.pk)];line=product.price*qty;total+=line;rows.append({'product':product,'quantity':qty,'total':line})
    return render(request,'marketplace/cart.html',{'rows':rows,'total':total,'currency':rows[0]['product'].currency if rows else 'JOD'})

@role_required('patient')
def cart_checkout(request):
    cart_data=request.session.get('cart',{})
    if not cart_data: return redirect('cart')
    p=request.user.profile
    products=list(Product.objects.filter(pk__in=cart_data).select_related('pharmacy'))
    if not products or len(products)!=len(cart_data): messages.error(request,'A product is no longer available. Update your basket.');return redirect('cart')
    merchant=products[0].pharmacy
    if any(x.pharmacy_id!=merchant.pk or x.currency!=products[0].currency for x in products): return JsonResponse({'error':'An order must use one pharmacy and currency.'},status=400)
    quote_rows=[{'id':x.pk,'quantity':cart_data[str(x.pk)],'price':str(x.price),'currency':x.currency} for x in products]
    form=CheckoutForm(request.POST or None,initial={'city':p.city,'address':p.address,'quote':quote_token(request.user,quote_rows)})
    del form.fields['slot'];del form.fields['quantity']
    total=sum((x.price*cart_data[str(x.pk)] for x in products),Decimal('0'))
    if request.method=='POST' and form.is_valid():
        with db_transaction.atomic():
            Profile.objects.filter(pk=merchant.pk).update(revision=F('revision')+1);merchant.refresh_from_db()
            products=list(Product.objects.filter(pk__in=cart_data).select_related('pharmacy'))
            current_rows=[{'id':x.pk,'quantity':cart_data[str(x.pk)],'price':str(x.price),'currency':x.currency} for x in products]
            if not valid_quote(form.cleaned_data['quote'],request.user,current_rows): form.add_error(None,'Prices or your basket changed, or the quote expired. Reload checkout to review the current total.')
            elif len(products)!=len(cart_data): form.add_error(None,'A basket item is no longer available.')
            elif merchant.verification!='approved' or not merchant.user.is_active: form.add_error(None,'This pharmacy is not currently available.')
            elif not merchant.serves(form.cleaned_data['city']): form.add_error('city','This pharmacy does not serve your city.')
            elif any(not x.active or x.stock<cart_data[str(x.pk)] or not 1<=cart_data[str(x.pk)]<=50 for x in products): form.add_error(None,'Stock or availability changed. Return to your basket to adjust quantities.')
            else:
                current=sum((x.price*cart_data[str(x.pk)] for x in products),Decimal('0'))
                if current!=total: form.add_error(None,'Prices changed. Review the current basket before submitting again.')
                else:
                    policy=MarketplacePolicy.current()
                    record=Transaction.objects.create(patient=request.user,merchant=merchant,kind='order',title=f'Pharmacy order · {len(products)} item types',quantity=sum(cart_data.values()),city=form.cleaned_data['city'],address=form.cleaned_data['address'],subtotal=current,total=current,currency=products[0].currency,commission_rate=policy.commission_percent if policy.currency==products[0].currency else None)
                    for product in products:
                        qty=cart_data[str(product.pk)]
                        Product.objects.filter(pk=product.pk).update(stock=F('stock')-qty,revision=F('revision')+1)
                        OrderItem.objects.create(transaction=record,product=product,name=product.name,quantity=qty,unit_price=product.price)
                    event(request.user,'Order submitted','Awaiting pharmacy acceptance · unpaid',record,[request.user,merchant.user]);request.session['cart']={}
                    Profile.objects.filter(pk=p.pk).update(city=form.cleaned_data['city'],address=form.cleaned_data['address'])
                    return redirect('record',pk=record.pk)
    return render(request,'marketplace/cart_checkout.html',{'form':form,'products':products,'total':total,'currency':products[0].currency,'merchant':merchant})

@role_required('patient')
def account(request):
    class AddressForm(forms.ModelForm):
        class Meta:
            model=SavedAddress;fields=['label','city','address']
        def clean_address(self):
            address=self.cleaned_data['address'].strip()
            if len(address)<8: raise forms.ValidationError('Enter a complete street and building address.')
            return address
    form=AddressForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        address=form.save(commit=False);address.patient=request.user;address.save();event(request.user,'Address saved',address.label);messages.success(request,'Address saved.');return redirect('account')
    return render(request,'marketplace/account.html',{'form':form,'addresses':SavedAddress.objects.filter(patient=request.user)})

@require_POST
@role_required('patient')
def address_action(request, pk):
    address=get_object_or_404(SavedAddress,pk=pk,patient=request.user)
    if request.POST.get('action')=='default': Profile.objects.filter(user=request.user).update(address=address.address,city=address.city)
    elif request.POST.get('action')=='delete': address.delete()
    else: return JsonResponse({'error':'Unknown address action'},status=400)
    return redirect('account')

class IssueForm(forms.Form):
    description=forms.CharField(min_length=15,max_length=1500,label='Describe your issue (do not include medical records)',widget=forms.Textarea(attrs={'rows':3}))

@require_POST
@login_required
def issue_open(request, pk):
    t=get_object_or_404(Transaction,pk=pk)
    if request.user.pk not in [t.patient_id,t.merchant.user_id]: return HttpResponseForbidden()
    form=IssueForm(request.POST)
    if form.is_valid():
        with db_transaction.atomic():
            issue=Issue.objects.create(transaction=t,opened_by=request.user,description=form.cleaned_data['description'])
            event(request.user,'Issue opened',f'Issue #{issue.pk} awaiting admin review',t,list(User.objects.filter(is_staff=True))+[request.user])
        messages.success(request,'Issue saved for admin review. No refund or payment action was performed.');return redirect('record',pk=pk)
    return render(request,'marketplace/record.html',{'record':t,'issue_form':form},status=400)

@require_POST
@role_required('admin')
def issue_resolve(request, pk):
    notes=request.POST.get('resolution','').strip()
    if len(notes)<15 or len(notes)>1500: return JsonResponse({'error':'Provide resolution notes between 15 and 1500 characters.'},status=400)
    with db_transaction.atomic():
        if not Issue.objects.filter(pk=pk,status='open').update(status='resolved',resolution=notes,resolved_by=request.user): return JsonResponse({'error':'Issue already resolved or missing.'},status=409)
        issue=Issue.objects.select_related('transaction').get(pk=pk)
        event(request.user,'Issue resolved',f'Issue #{pk} resolution recorded; no financial action',issue.transaction,[issue.transaction.patient,issue.transaction.merchant.user])
    messages.success(request,'Resolution saved.');return redirect('operations')
