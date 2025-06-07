from django.db import models
from django.contrib.auth.models import User
import random
from decimal import Decimal
from users.models import CustomUser  # Adjust the import based on your user model location
# Create your models here.



class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='static/images/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    

class Items(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to='static/images/', blank=True, null=True)
    rating=models.FloatField(default=0.0)
    category = models.ForeignKey(Category, related_name='items', on_delete=models.CASCADE, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    def update_rating(self):
        foo_ratings = self.foo_ratings.all()  # Use related name
        avg_rating = sum(r.rating for r in foo_ratings) / len(foo_ratings) if foo_ratings else 0
        self.rating = avg_rating
        self.save()
    


class FooRating(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    menu = models.ForeignKey(Items, related_name='foo_ratings', on_delete=models.CASCADE)
    rating = models.IntegerField(default=1)

    class Meta:
        unique_together = ('user', 'menu')

    def __str__(self):
        return f'{self.user} - {self.menu} - {self.rating}'
    


class Order(models.Model):  
    ORDER_STATUS = [  
        ('in_process', 'In Process'),  
        ('on_way','On Way'),
        ('delivered', 'Delivered'),
        ('done', 'Done'),  
        ('cancelled', 'Cancelled'),
        ('paid', 'Paid'),
    ]  

    order_number = models.CharField(max_length=1000, unique=True)  
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    status = models.CharField(max_length=10, choices=ORDER_STATUS, default='in_process')  
    created_at = models.DateTimeField(auto_now_add=True)  
    status_pay = models.CharField(max_length=20, default="PENDING")
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    refund_id = models.CharField(max_length=100, blank=True, null=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_status = models.CharField(max_length=100, blank=True, null=True)


    def save(self, *args, **kwargs):  
        if not self.order_number:  
            self.order_number = str(random.randint(10000, 99999))  # Generate random 5-digit order number  
        super(Order, self).save(*args, **kwargs)  

    def __str__(self):  
        return f"Order {self.order_number} - {self.user.username}"



class Cart(models.Model):  
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)  
    items = models.ManyToManyField(Items, through='CartItem')  
    created_at = models.DateTimeField(auto_now_add=True)  
    order = models.OneToOneField(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')  

    def total_price(self):  
        total = Decimal('0.00')  # Initialize as Decimal  
        for cart_item in self.cart_items.all():  
            total += cart_item.total_price()  # Ensure total_price() returns a Decimal  
        return total  

    def __str__(self):  
        return f"Cart for {self.user.username}" + (f" - Order {self.order.order_number}" if self.order else "")  


class CartItem(models.Model):  
    cart = models.ForeignKey(Cart, related_name='cart_items', on_delete=models.CASCADE)  
    menu_item = models.ForeignKey(Items, on_delete=models.CASCADE)  
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'menu_item')

    def total_price(self):  
        return self.menu_item.price * self.quantity  



class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Items, on_delete=models.CASCADE)  # or MenuItem etc.
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # single item price

    def total_price(self):
        return self.quantity * self.price