from django.contrib import admin
from .models import Items, FooRating, Cart, CartItem, Order, Category


admin.site.register(Items)
admin.site.register(FooRating)
admin.site.register(Cart)
admin.site.register(Order)
admin.site.register(Category)