from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
import razorpay
from django.views.decorators.http import require_POST
from .models import Items, Cart, CartItem, Order, OrderItem, Category
from django.core.paginator import Paginator
import json
import traceback
from django.urls import reverse
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login, get_backends
from django.contrib import messages
from django.contrib.auth.views import PasswordResetView
from django.core.mail import send_mail
from django.utils.http import url_has_allowed_host_and_scheme
from users.forms import LoginForm , RegisterForm

# Helper to get or create the active cart (order=None) for a user
def get_or_create_active_cart(user):
    cart = Cart.objects.filter(user=user, order__isnull=True).first()
    if not cart:
        cart = Cart.objects.create(user=user)
    return cart


class HomeView(View):
    def get(self, request):
        items = Items.objects.all()
        category= Category.objects.all()
        cart_quantities = {}

        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user, order__isnull=True).first()
            if cart:
                cart_items = CartItem.objects.filter(cart=cart)
                cart_quantities = {ci.menu_item.id: ci.quantity for ci in cart_items}

        context = {
            'items': items,
            'cart_quantities': cart_quantities,
            'category': category,
        }
        return render(request, "home.html", context)

@login_required
def view_cart(request):
    cart = Cart.objects.filter(user=request.user, order__isnull=True).first()
    items_qs = cart.cart_items.select_related('menu_item') if cart else []

    # Paginate cart items
    paginator = Paginator(items_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    total_price = sum(item.quantity * item.menu_item.price for item in items_qs)
    total_quantity = sum(item.quantity for item in items_qs)

    total_price_in_paise = int(total_price * 100)

    # Only proceed if total is ≥ ₹1
    razorpay_order = None
    if total_price_in_paise >= 100:
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        order_data = {
            'amount': total_price_in_paise,
            'currency': 'INR',
            'payment_capture': '1'
        }
        razorpay_order = client.order.create(data=order_data)

    context = {
        'items': page_obj,
        'total_price': total_price,
        'total_price_in_paise': total_price_in_paise,
        'total_quantity': total_quantity,
        'razorpay_order_id': razorpay_order['id'] if razorpay_order else None,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'page_obj': page_obj,
        'show_checkout': total_price_in_paise >= 100,
    }
    return render(request, 'view_cart.html', context)

@csrf_exempt
def toggle_cart_item(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'User not authenticated'}, status=403)

    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        action = request.POST.get('action')

        if not item_id or not action:
            return JsonResponse({'success': False, 'error': 'Missing item_id or action'}, status=400)

        # if action not in ['add', 'remove']:
        #     return JsonResponse({'success': False, 'error': 'Invalid action specified'}, status=400)

        try:
            item = Items.objects.get(id=item_id)
        except Items.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Item not found'}, status=404)

        cart = get_or_create_active_cart(request.user)

        cart_item, item_was_newly_created_in_cart = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=item,
            defaults={'quantity': 0}
        )

        if action == 'add':
            cart_item.quantity += 1
        elif action == 'remove':
            cart_item.quantity -= 1

        if cart_item.quantity > 0:
            cart_item.save()
            final_quantity = cart_item.quantity
            item_is_in_cart = True
        else:
            cart_item.delete()
            final_quantity = 0
            item_is_in_cart = False

        return JsonResponse({
            'success': True,
            'quantity': final_quantity,
            'in_cart': item_is_in_cart,
            'item_id': item_id
        })

    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@login_required
def add_to_cart(request, item_id):
    item = get_object_or_404(Items, id=item_id)
    cart = get_or_create_active_cart(request.user)

    cart_item, item_was_created_in_cart = CartItem.objects.get_or_create(
        cart=cart,
        menu_item=item
    )

    if not item_was_created_in_cart:
        cart_item.quantity += 1
        cart_item.save()

    return redirect('view_cart')


@login_required
def checkout_cart(request):
    cart = Cart.objects.filter(user=request.user, order__isnull=True).first()
    if not cart or not cart.cart_items.exists():
        return JsonResponse({'error': 'Cart is empty'}, status=400)

    total_price = cart.total_price()
    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
    order_data = {
        'amount': int(total_price * 100),
        'currency': 'INR',
        'payment_capture': '1'
    }
    razorpay_order = client.order.create(data=order_data)

    return JsonResponse({
        'razorpay_order_id': razorpay_order['id'],
        'amount': int(total_price * 100),
        'currency': 'INR',
        'key': settings.RAZORPAY_KEY_ID,
    })




@csrf_exempt
@login_required
def payment_success(request):
    if request.method == "POST":
        data = request.POST
        cart = Cart.objects.filter(user=request.user, order__isnull=True).first()
        if not cart:
            return JsonResponse({'error': 'No cart found'}, status=400)

        order = Order.objects.create(
            user=request.user,
            total_amount=cart.total_price(),
            status='in_process',
            status_pay='PAID',
            razorpay_payment_id=data.get("razorpay_payment_id")
        )

        # ✅ Create OrderItem entries from cart items
        for item in cart.cart_items.all():
            OrderItem.objects.create(
                order=order,
                product=item.menu_item,
                quantity=item.quantity,
                price=item.total_price(),
            )

        cart.order = order
        cart.save()

        cart.delete()  # Clear the cart after successful payment
        receipt_url = reverse('order_receipt', args=[order.order_number])
        return JsonResponse({'success': True, 'order_id': order.order_number, 'redirect_url': receipt_url})


    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


@require_POST
@login_required
def update_cart_quantity(request):
    cart = Cart.objects.filter(user=request.user, order__isnull=True).first()
    if not cart:
        return JsonResponse({'error': 'Cart not found'}, status=404)

    item_id = request.POST.get('item_id')
    action = request.POST.get('action')

    try:
        cart_item = cart.cart_items.get(menu_item_id=item_id)
    except CartItem.DoesNotExist:
        return JsonResponse({'error': 'Item not found in cart'}, status=404)

    if action == 'increment':
        cart_item.quantity += 1
    elif action == 'decrement':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
        else:
            cart_item.delete()
            return JsonResponse({'removed': True})

    cart_item.save()

    total_price = cart.total_price()

    return JsonResponse({
        'quantity': cart_item.quantity,
        'item_total': float(cart_item.total_price()),
        'cart_total': float(total_price)
    })


def order_list(request):
    orders=Order.objects.filter(status='in_process').order_by('-created_at')
    context={
        'order':orders,
    }
    return render(request, 'order_list.html', context)




@login_required
@require_POST
def update_order_status(request, order_id):
    try:
        new_status = request.POST.get('status')
        order = Order.objects.get(id=order_id, user=request.user)

        allowed_statuses = [choice[0] for choice in Order.ORDER_STATUS]
        if new_status not in allowed_statuses:
            return JsonResponse({'status': 'error', 'message': 'Invalid status'}, status=400)

        if new_status == 'done' and order.status != 'in_process':
            return JsonResponse({
                'status': 'error',
                'message': 'Only orders in process can be marked as done.'
            }, status=400)

        order.status = new_status
        order.save()
        return JsonResponse({'status': 'success', 'new_status': order.status})

    except Order.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Order not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)



@csrf_exempt
@require_POST
def cancel_order(request):
    try:
        data = json.loads(request.body)
        order_id = data.get("order_id")

        if not order_id:
            return JsonResponse({"status": "error", "message": "Order ID is required."}, status=400)

        order = Order.objects.get(id=order_id)

        if not order.razorpay_payment_id:
            return JsonResponse({"status": "error", "message": "No payment ID found for this order."}, status=400)

        # Use total_amount for refund
        refund_amount = float(order.total_amount)
        refund_amount_paise = int(refund_amount * 100)

        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

        refund = client.payment.refund(order.razorpay_payment_id, {
            "amount": refund_amount_paise
        })

        # Update order with refund info
        order.status = 'cancelled'
        order.refund_id = refund.get("id")
        order.refund_amount = refund_amount_paise / 100
        order.refund_status = refund.get("status")
        order.save()

        return JsonResponse({
            "status": "success",
            "message": "Order cancelled and refunded (full amount).",
            "refund": {
                "refund_id": order.refund_id,
                "amount": order.refund_amount,
                "status": order.refund_status
            }
        })

    except Order.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Order not found."}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON."}, status=400)
    except razorpay.errors.BadRequestError as e:
        return JsonResponse({"status": "error", "message": f"Refund failed: {str(e)}"}, status=400)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    



@login_required
def order_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Get all items related to this order
    cart_items = OrderItem.objects.filter(order=order)

    # Calculate total (you may already store this in order.total_amount)
    order_total = sum(item.price for item in cart_items)

    return render(request, 'order_details.html', {
        'order': order,
        'cart_items': cart_items,
        'order_total': order_total
    })


@require_POST
@login_required
def clear_cart(request):
    cart = Cart.objects.filter(user=request.user, order__isnull=True).first()
    if cart:
        cart.cart_items.all().delete()
        cart.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'message': 'No active cart found'})

def my_orders(request):
    if not request.user.is_authenticated:
        return redirect('login')

    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    context = {
        'orders': orders,
    }
    return render(request, 'my_orders.html', context)

def category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    items = Items.objects.filter(category=category)

    cart_quantities = {}
    if request.user.is_authenticated:
        cart = Cart.objects.filter(user=request.user, order__isnull=True).first()
        if cart:
            cart_items = CartItem.objects.filter(cart=cart)
            cart_quantities = {ci.menu_item.id: ci.quantity for ci in cart_items}

    context = {
        'items': items,
        'category': category,
        'cart_quantities': cart_quantities,
    }
    return render(request, 'category.html', context)



def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)

            request.session.save()  # Ensure session_key is created
            user.current_session_key = request.session.session_key
            user.save(update_fields=['current_session_key'])

            if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
            return redirect('home')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form, 'next': next_url})



def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # ✅ Fix: Set the backend explicitly
            backend = get_backends()[0]  # Or whichever you want
            user.backend = f"{backend.__module__}.{backend.__class__.__name__}"
            auth_login(request, user)
            messages.success(request, 'Registration successful.')
            return redirect('home')
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})