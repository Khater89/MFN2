from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    path('',views.home,name='home'),path('providers/<int:pk>/',views.profile,name='profile'),
    path('register/',views.register,name='register'),path('login/',LoginView.as_view(template_name='marketplace/login.html'),name='login'),path('logout/',LogoutView.as_view(),name='logout'),
    path('onboarding/',views.onboarding,name='onboarding'),path('dashboard/',views.dashboard,name='dashboard'),
    path('checkout/<str:kind>/<int:pk>/',views.checkout,name='checkout'),path('requests/<uuid:pk>/',views.record,name='record'),path('requests/<uuid:pk>/status/',views.transition,name='transition'),path('requests/<uuid:pk>/payment/',views.payment,name='payment'),
    path('catalog/new/',views.product_edit,name='product_add'),path('catalog/<int:pk>/',views.product_edit,name='product_edit'),path('services/new/',views.service_add,name='service_add'),path('services/<int:pk>/availability/',views.slot_add,name='slot_add'),
    path('services/<int:pk>/edit/',views.service_add,name='service_edit'),path('availability/<int:pk>/remove/',views.slot_remove,name='slot_remove'),
    path('cart/',views.cart,name='cart'),path('cart/add/<int:pk>/',views.cart_add,name='cart_add'),path('cart/checkout/',views.cart_checkout,name='cart_checkout'),
    path('account/',views.account,name='account'),path('account/addresses/<int:pk>/',views.address_action,name='address_action'),
    path('requests/<uuid:pk>/issue/',views.issue_open,name='issue_open'),path('operations/issues/<int:pk>/resolve/',views.issue_resolve,name='issue_resolve'),
    path('operations/',views.operations,name='operations'),path('operations/review/<int:pk>/',views.review,name='review'),path('licenses/<int:pk>/',views.license_download,name='license_download'),
]
