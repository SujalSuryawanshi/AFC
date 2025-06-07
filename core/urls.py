
from django.contrib import admin
from django.urls import path, include
from .views import HomeView
from django.contrib.auth import views as auth_views
from . import views
urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    # path('add_to_cart/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('toggle-cart-item/', views.toggle_cart_item, name='toggle_cart_item'),
    path('checkout/', views.checkout_cart, name='checkout_cart'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('cart/update-quantity/', views.update_cart_quantity, name='update_cart_quantity'),
    path('cart/toggle/', views.toggle_cart_item, name='toggle_cart_item'),
    path("order_list/", views.order_list, name="order_list"),
    path('update-order-status/<int:order_id>/', views.update_order_status, name='update_order_status'),
    path('cancel-order/', views.cancel_order, name='cancel_order'),
    path('orders/receipt/<int:order_id>/', views.order_receipt, name='order_receipt'),
    path('clear-cart/', views.clear_cart, name='clear_cart'),
    path("my-orders/", views.my_orders , name="my_orders"),
    path("category-items/<int:category_id>", views.category, name="category_items"),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
        path('register/', views.register, name='register'),





]
