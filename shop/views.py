from decimal import Decimal
import urllib.parse
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.utils.text import slugify
from datetime import datetime, time as dtime
import random
import time
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .forms import CategoryForm, CheckoutForm, ProductForm, RegisterForm
from .models import Category, Order, OrderItem, Product, Profile, ShopSettings, ProductImage


def is_owner_or_staff(user):
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    profile = Profile.objects.filter(user=user).first()
    return profile is not None and profile.role == "owner"


def home(request):
    featured = Product.objects.filter(featured=True, stock__gt=0)[:8]
    new_arrivals = Product.objects.filter(is_new=True,
stock__gt=0)[:8]
    categories = Category.objects.all()[:6]
    return render(request, "home.html", {
        "featured": featured,
        "new_arrivals": new_arrivals,
        "categories": categories,
    })


def shop(request):
    products = Product.objects.filter(stock__gt=0)
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    sort = request.GET.get("sort", "newest")

    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))
    if category:
        products = products.filter(category__slug=category)

    if sort == "price_low":
        products = products.order_by("price")
    elif sort == "price_high":
        products = products.order_by("-price")
    else:
        products = products.order_by("-created_at")

    return render(request, "shop.html", {
        "products": products,
        "categories": Category.objects.all(),
        "active_category": category,
        "query": q,
        "sort": sort,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related = Product.objects.filter(category=product.category,
stock__gt=0).exclude(id=product.id)[:4]
    return render(request, "product_detail.html", {"product": product,
"related": related})


def _cart(request):
    return request.session.setdefault("cart", {})


def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    size = request.POST.get("size", "")
    quantity = max(int(request.POST.get("quantity", 1)), 1)

    if quantity > product.stock:
        messages.error(request, "Only limited stock is available.")
        return redirect("product_detail", slug=product.slug)

    cart = _cart(request)
    key = f"{product.id}:{size}"
    current = cart.get(key, {"product_id": product.id, "size": size,"quantity": 0})
    current["quantity"] += quantity
    current["quantity"] = min(current["quantity"], product.stock)
    cart[key] = current
    request.session.modified = True
    messages.success(request, f"{product.name} added to your bag.")
    return redirect(request.POST.get("next", "cart"))


def cart(request):
    cart_data = _cart(request)
    items = []
    subtotal = Decimal("0")
    # total_tax = Decimal("0")

    for key, item in cart_data.items():
        product = Product.objects.filter(id=item["product_id"]).first()
        if not product:
            continue
        item_subtotal = product.price * item["quantity"]
        # item_tax = (item_subtotal * (product.gst_rate /Decimal("100"))).quantize(Decimal("0.01"))

        subtotal += item_subtotal
        # total_tax += item_tax

        items.append({
            "key": key,
            "product": product,
            "size": item.get("size", ""),
            "quantity": item["quantity"],
            "subtotal": item_subtotal,
            "gst_rate": product.gst_rate,
            # "gst_amount": item_tax,
            "item_total": item_subtotal ,
        })

    grand_total = subtotal 
    return render(request, "cart.html", {
        "items": items,
        "subtotal": subtotal,
        # "total_tax": total_tax,
        "total": grand_total,
    })


def update_cart(request, key):
    cart_data = _cart(request)
    if key in cart_data:
        quantity = max(int(request.POST.get("quantity", 1)), 1)
        product = get_object_or_404(Product,
id=cart_data[key]["product_id"])
        cart_data[key]["quantity"] = min(quantity, product.stock)
        request.session.modified = True
    return redirect("cart")


def remove_from_cart(request, key):
    cart_data = _cart(request)
    cart_data.pop(key, None)
    request.session.modified = True
    return redirect("cart")


def _send_otp_email(email, otp_code):
    subject = "Your Verification Code - Follow Me Boutique"
    message = (
        f"Hello,\n\n"
        f"Thank you for joining Follow Me Boutique!\n"
        f"Your one-time verification code (OTP) is: {otp_code}\n\n"
        f"This code is valid for 10 minutes. Please do not share this code with anyone.\n\n"
        f"Warm regards,\n"
        f"Follow Me Boutique Team"
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@followmeboutique.com")
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email,
        recipient_list=[email],
        fail_silently=False,
    )


def register(request):
    next_url = request.GET.get("next") or request.POST.get("next") or "home"
    if request.user.is_authenticated:
        return redirect(next_url)

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            # Generate 6-digit OTP
            otp_code = f"{random.randint(100000, 999999)}"
            email = form.cleaned_data.get("email")

            try:
                _send_otp_email(email, otp_code)
            except Exception as e:
                messages.error(
                    request,
                    f"Unable to send verification email. Please check your email address or SMTP configuration: {e}"
                )
                return render(request, "auth/register.html", {"form": form, "next": next_url})

            # Store sanitized form registration data & OTP timestamp in session
            request.session["pending_registration"] = {
                "post_data": request.POST.dict(),
                "email": email,
                "otp": otp_code,
                "expires_at": int(time.time()) + 600,  # 10 minutes
                "next": next_url,
            }
            request.session.modified = True
            messages.success(request, f"A 6-digit verification code has been sent to {email}.")
            return redirect("verify_registration_otp")
    else:
        form = RegisterForm()

    return render(request, "auth/register.html", {"form": form, "next": next_url})


def verify_registration_otp(request):
    if request.user.is_authenticated:
        return redirect("home")

    pending = request.session.get("pending_registration")
    if not pending:
        messages.warning(request, "No pending registration found. Please fill in the sign-up form.")
        return redirect("register")

    next_url = pending.get("next", "home")
    email = pending.get("email", "")

    if request.method == "POST":
        submitted_otp = request.POST.get("otp", "").strip()
        expected_otp = pending.get("otp", "")
        expires_at = pending.get("expires_at", 0)

        if int(time.time()) > expires_at:
            messages.error(request, "The verification code has expired. Please request a new code.")
            return render(request, "auth/verify_otp.html", {"email": email})

        if submitted_otp != expected_otp:
            messages.error(request, "Invalid verification code. Please check and try again.")
            return render(request, "auth/verify_otp.html", {"email": email})

        # OTP is valid, proceed with creating user account
        post_data = pending.get("post_data", {})
        form = RegisterForm(post_data)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, role="customer")

            # Clean session
            request.session.pop("pending_registration", None)
            request.session.modified = True

            login(request, user)
            messages.success(request, "Account verified and created successfully! Welcome to Follow Me Boutique.")
            return redirect(next_url)
        else:
            errors = " ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
            messages.error(request, f"Could not create account: {errors}")
            return redirect("register")

    return render(request, "auth/verify_otp.html", {"email": email})


def resend_registration_otp(request):
    pending = request.session.get("pending_registration")
    if not pending:
        messages.warning(request, "No registration session found. Please register again.")
        return redirect("register")

    email = pending.get("email")
    otp_code = f"{random.randint(100000, 999999)}"

    try:
        _send_otp_email(email, otp_code)
        pending["otp"] = otp_code
        pending["expires_at"] = int(time.time()) + 600
        request.session["pending_registration"] = pending
        request.session.modified = True
        messages.success(request, f"A new verification code has been sent to {email}.")
    except Exception as e:
        messages.error(request, f"Failed to resend code: {e}")

    return redirect("verify_registration_otp")


def login_view(request):
    from django.contrib.auth import authenticate
    next_url = request.GET.get("next") or request.POST.get("next") or "home"
    if request.user.is_authenticated:
        return redirect(next_url)
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect(next_url)
        messages.error(request, "Invalid username or password.")
    return render(request, "auth/login.html", {"next": next_url})


def logout_view(request):
    logout(request)
    return redirect("home")


@login_required
def checkout(request):
    cart_data = _cart(request)
    if not cart_data:
        return redirect("shop")

    items = []
    subtotal = Decimal("0")
    # total_tax = Decimal("0")

    for key, item in cart_data.items():
        product = get_object_or_404(Product, id=item["product_id"])
        item_sub = product.price * item["quantity"]
        item_tax = Decimal("0.00")
        subtotal += item_sub
        items.append((key, product, item, item_sub, item_tax))

    grand_total = subtotal 

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.subtotal = subtotal
            order.total_tax = Decimal("0.00")
            order.cgst = Decimal("0.00")
            order.sgst = Decimal("0.00")
            order.igst = Decimal("0.00")
            order.total = grand_total

            # Pre-validate stock for ALL items before modifying database
            for key, product, item, item_sub, item_tax in items:
                if product.stock < item["quantity"]:
                    messages.error(request, f"{product.name} is no longer available in that quantity.")
                    return redirect("cart")

            with transaction.atomic():
                order.save()
                for key, product, item, item_sub, item_tax in items:
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        size=item.get("size", ""),
                        quantity=item["quantity"],
                        price=product.price,
                        gst_rate=Decimal("0.00"),
                        gst_amount=Decimal("0.00"),
                    )
                    product.stock -= item["quantity"]
                    product.save(update_fields=["stock"])

            request.session["cart"] = {}
            request.session.modified = True
            return redirect("payment_page", order_id=order.id)
    else:
        form = CheckoutForm(initial={
            "full_name": request.user.get_full_name() or request.user.username,
            "phone": "",
            "state": "Tamil Nadu",
        })

    return render(request, "checkout.html", {
        "form": form,
        "items": items,
        "subtotal": subtotal,
        # "total_tax": total_tax,
        "total": grand_total,
    })


@login_required
def payment_page(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    # Safeguard 1: Do not allow payment submission if order is already Paid or Cancelled
    if order.payment_status.strip().lower() == "paid":
        messages.info(request, f"Order #{order.id} is already marked as Paid and verified.")
        return redirect("order_success", order_id=order.id)

    if order.status == "cancelled":
        messages.error(request, f"Order #{order.id} has been cancelled. Payment cannot be accepted.")
        return redirect("my_orders")

    settings_obj = ShopSettings.objects.first() or ShopSettings.objects.create()

    upi_id = settings_obj.upi_id or "yourboutique@upi"
    upi_name = settings_obj.upi_name or "FOLLOW ME Boutique"
    amount = f"{order.total:.2f}"
    note = f"Order #{order.id} Boutique"

    # Construct standard NPCI compliant Merchant UPI URI
    upi_params = {
        "pa": upi_id,
        "pn": upi_name,
        "mc": "5691",
        "tr": f"ORD{order.id}",
        "am": amount,
        "cu": "INR",
        "tn": f"Order #{order.id}",
        "mode": "02",
    }
    encoded_params = urllib.parse.urlencode(upi_params)
    upi_url = f"upi://pay?{encoded_params}"

    # App-specific direct intent URLs
    gpay_url = f"gpay://upi/pay?{encoded_params}"
    phonepe_url = f"phonepe://pay?{encoded_params}"
    paytm_url = f"paytmmp://pay?{encoded_params}"

    # High-resolution QR code
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={urllib.parse.quote(upi_url)}"

    if request.method == "POST":
        utr = request.POST.get("payment_reference", "").strip()
        if not utr:
            messages.error(request, "Please enter your 12-digit UTR or Transaction ID.")
        elif len(utr) < 8 or len(utr) > 30:
            messages.error(request, "Invalid reference format. Standard UPI UTR / Transaction IDs are between 8 and 30 characters.")
        elif Order.objects.filter(payment_reference__iexact=utr).exclude(pk=order.pk).exists():
            # Safeguard 2: Duplicate UTR detection across orders
            messages.error(request, "This Transaction ID / UTR has already been submitted for another order. Please check and provide your unique receipt reference.")
        else:
            order.payment_reference = utr
            order.payment_status = "Submitted / Under Verification"
            order.save(update_fields=["payment_reference", "payment_status"])
            messages.success(request, "Payment reference submitted! We will verify and process your order.")
            return redirect("order_success", order_id=order.id)

    return render(request, "payment.html", {
        "order": order,
        "upi_url": upi_url,
        "gpay_url": gpay_url,
        "phonepe_url": phonepe_url,
        "paytm_url": paytm_url,
        "qr_code_url": qr_code_url,
        "upi_id": upi_id,
        "upi_name": upi_name,
        "amount": amount,
    })


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "order_success.html", {"order": order})


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user)
    return render(request, "my_orders.html", {"orders": orders})


@login_required
def download_receipt(request, order_id):
    if is_owner_or_staff(request.user):
        order = get_object_or_404(Order, id=order_id)
    else:
        order = get_object_or_404(Order, id=order_id, user=request.user)

    # Strictly generate invoice only after successful payment completion
    if order.payment_status.strip().lower() != "paid":
        if is_owner_or_staff(request.user):
            messages.warning(
                request,
                f"Invoice locked: Order #{order.id} is currently '{order.payment_status}'. Invoices are generated only after payment is verified and marked as 'Paid'."
            )
            return redirect("owner_order_detail", order_id=order.id)
        else:
            messages.warning(
                request,
                f"Your invoice for Order #{order.id} will be generated once payment verification is completed. Current status: '{order.payment_status}'."
            )
            return redirect("my_orders")

    shop_settings = ShopSettings.objects.first()
    return render(request, "receipt.html", {
        "order": order,
        "shop_settings": shop_settings,
    })


# ------------------- OWNER / ADMIN SECTION (STRICTLY HIDDEN) -------------------

def owner_required(view_func):
    """Decorator ensuring only owner or staff can access."""
    def _wrapped_view(request, *args, **kwargs):
        if not is_owner_or_staff(request.user):
            messages.error(request, "Access restricted. Only store administrators can access this page.")
            return redirect("home")
        return view_func(request, *args, **kwargs)
    return login_required(_wrapped_view)


@owner_required
def owner_dashboard(request):
    orders = Order.objects.all()
    revenue = orders.exclude(status="cancelled").aggregate(total=Sum("total"))["total"] or Decimal("0")
    context = {
        "products_count": Product.objects.count(),
        "categories_count": Category.objects.count(),
        "orders_count": orders.count(),
        "customers_count": User.objects.count(),
        "revenue": revenue,
        "recent_orders": orders[:8],
        "low_stock": Product.objects.filter(stock__lte=5).order_by("stock")[:8],
    }
    return render(request, "owner/dashboard.html", context)


@owner_required
def owner_products(request):
    products = Product.objects.select_related("category").all()
    q = request.GET.get("q", "").strip()
    sort = request.GET.get("sort", "newest")

    if q:
        products = products.filter(Q(name__icontains=q) | Q(description__icontains=q))

    if sort == "price_low":
        products = products.order_by("price")
    elif sort == "price_high":
        products = products.order_by("-price")
    elif sort == "stock_low":
        products = products.order_by("stock")
    else:
        products = products.order_by("-created_at")

    return render(request, "owner/products.html", {
        "products": products,
        "query": q,
        "sort": sort,
    })


@owner_required
def owner_product_new(request):
    if request.method == "POST":
        try:
            form = ProductForm(request.POST, request.FILES)
            if form.is_valid():
                product = form.save(commit=False)
                base_slug = (slugify(product.name) or "item")[:40]
                slug = base_slug
                counter = 1
                while Product.objects.filter(slug=slug).exists():
                    slug = f"{base_slug[:35]}-{counter}"
                    counter += 1
                product.slug = slug[:50]
                product.save()

                for f in request.FILES.getlist("gallery_images"):
                    try:
                        ProductImage.objects.create(product=product, image=f)
                    except Exception as img_err:
                        messages.warning(request, f"Could not save a gallery image: {img_err}")

                messages.success(request, f"Product '{product.name}' added successfully.")
                return redirect("owner_products")
            else:
                err_list = [f"{field}: {err[0]}" for field, err in form.errors.items()]
                messages.error(request, f"Could not add product. Please check: {'; '.join(err_list)}")
        except Exception as e:
            import logging
            logging.exception("Error adding product")
            messages.error(request, f"Error saving product: {str(e)}")
    else:
        form = ProductForm()
    return render(request, "owner/product_form.html", {
        "form": form,
        "heading": "Add a new product",
        "button": "Save product",
    })


@owner_required
def owner_product_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        try:
            if request.POST.get("clear_main_image") == "1":
                try:
                    if product.image:
                        product.image.delete(save=False)
                except Exception:
                    pass
                product.image = None
                product.save(update_fields=["image"])

            form = ProductForm(request.POST, request.FILES, instance=product)
            if form.is_valid():
                product = form.save(commit=False)

                # Synchronize slug safely without exceeding 50 chars
                base_slug = (slugify(product.name) or "item")[:40]
                if not product.slug or not product.slug.startswith(base_slug):
                    slug = base_slug
                    counter = 1
                    while Product.objects.filter(slug=slug).exclude(pk=product.pk).exists():
                        slug = f"{base_slug[:35]}-{counter}"
                        counter += 1
                    product.slug = slug[:50]

                product.save()

                # Handle additional gallery photo uploads safely
                for f in request.FILES.getlist("gallery_images"):
                    try:
                        ProductImage.objects.create(product=product, image=f)
                    except Exception as img_err:
                        messages.warning(request, f"Could not save a gallery image: {img_err}")

                messages.success(request, f"Product '{product.name}' updated successfully.")
                return redirect("owner_products")
            else:
                err_list = [f"{field}: {err[0]}" for field, err in form.errors.items()]
                messages.error(request, f"Could not update product. Please check: {'; '.join(err_list)}")
        except Exception as e:
            import logging
            logging.exception("Error updating product %s", product_id)
            messages.error(request, f"Error updating product: {str(e)}")
    else:
        form = ProductForm(instance=product)

    return render(request, "owner/product_form.html", {
        "form": form,
        "heading": f"Edit {product.name}",
        "button": "Save changes",
        "product": product,
    })


@owner_required
def owner_product_delete_gallery_image(request, image_id):
    img = get_object_or_404(ProductImage, id=image_id)
    product_id = img.product_id
    if request.method == "POST":
        try:
            if img.image:
                img.image.delete(save=False)
        except Exception:
            pass
        img.delete()
        messages.success(request, "Photo removed from gallery.")
    return redirect("owner_product_edit", product_id=product_id)


@owner_required
def owner_product_delete(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        name = product.name
        product.delete()
        messages.success(request, f"Product '{name}' was deleted.")
    return redirect("owner_products")


# Category Management
@owner_required
def owner_categories(request):
    from django.db.models import Count
    categories = Category.objects.annotate(product_count=Count("product")).order_by("name")
    return render(request, "owner/categories.html", {"categories": categories})


@owner_required
def owner_category_new(request):
    form = CategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cat = form.save()
        messages.success(request, f"Category '{cat.name}' created successfully.")
        return redirect("owner_categories")
    return render(request, "owner/category_form.html", {
        "form": form,
        "heading": "Add New Category",
        "button": "Create Category",
    })


@owner_required
def owner_category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        cat = form.save()
        messages.success(request, f"Category '{cat.name}' updated successfully.")
        return redirect("owner_categories")
    return render(request, "owner/category_form.html", {
        "form": form,
        "heading": f"Edit Category: {category.name}",
        "button": "Save Changes",
        "category": category,
    })


@owner_required
def owner_category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == "POST":
        cat_name = category.name
        category.delete()
        messages.success(request, f"Category '{cat_name}' was deleted.")
    return redirect("owner_categories")


# Customer & Role Management
@owner_required
def owner_customers(request):
    from django.db.models import Count, Sum
    customers = User.objects.annotate(
        order_count=Count("orders"),
        total_spent=Sum("orders__total")
    ).select_related("profile").order_by("-date_joined")
    return render(request, "owner/customers.html", {"customers": customers})


@owner_required
def owner_customer_toggle_role(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        if target_user == request.user:
            messages.error(request, "You cannot modify your own role.")
            return redirect("owner_customers")
        profile, _ = Profile.objects.get_or_create(user=target_user)
        if profile.role == "owner":
            profile.role = "customer"
            target_user.is_staff = False
            target_user.is_superuser = False
            target_user.save(update_fields=["is_staff", "is_superuser"])
            profile.save()
            messages.success(request, f"User '{target_user.username}' is now a Customer.")
        else:
            profile.role = "owner"
            target_user.is_staff = True
            target_user.is_superuser = True
            target_user.save(update_fields=["is_staff", "is_superuser"])
            profile.save()
            messages.success(request, f"User '{target_user.username}' is now a Business Owner with full admin access.")
    return redirect("owner_customers")


@owner_required
def owner_orders(request):
    orders = Order.objects.all().select_related("user")

    # Search query (by Order ID, Customer Name, Phone, Pincode, or Payment Reference)
    q = request.GET.get("q", "").strip()
    if q:
        orders = orders.filter(
            Q(id__icontains=q)
            | Q(full_name__icontains=q)
            | Q(phone__icontains=q)
            | Q(pincode__icontains=q)
            | Q(payment_reference__icontains=q)
            | Q(user__username__icontains=q)
        )

    # Fulfillment Status filter
    status = request.GET.get("status", "").strip()
    if status and status != "all":
        orders = orders.filter(status=status)

    # Payment Status filter
    payment_status = request.GET.get("payment_status", "").strip()
    if payment_status and payment_status != "all":
        orders = orders.filter(payment_status=payment_status)

    # Date range filters (YYYY-MM-DD)
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if date_from and date_to:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d")
            d_to = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            if d_from > d_to:
                messages.error(request, "'From Date' cannot be after 'To Date'. Please select a valid date range.")
                date_from = ""
                date_to = ""
            else:
                orders = orders.filter(created_at__gte=d_from, created_at__lte=d_to)
        except ValueError:
            pass
    elif date_from:
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d")
            orders = orders.filter(created_at__gte=d_from)
        except ValueError:
            pass
    elif date_to:
        try:
            d_to = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            orders = orders.filter(created_at__lte=d_to)
        except ValueError:
            pass

    # Quick preset filter (e.g. today, last 7 days, this month)
    preset = request.GET.get("preset", "").strip()
    now = timezone.now()
    if preset == "today":
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        orders = orders.filter(created_at__gte=start_of_day)
    elif preset == "week":
        seven_days_ago = now - timezone.timedelta(days=7)
        orders = orders.filter(created_at__gte=seven_days_ago)
    elif preset == "month":
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        orders = orders.filter(created_at__gte=start_of_month)

    # Sorting
    sort = request.GET.get("sort", "newest")
    if sort == "oldest":
        orders = orders.order_by("created_at")
    elif sort == "highest":
        orders = orders.order_by("-total")
    elif sort == "lowest":
        orders = orders.order_by("total")
    else:
        orders = orders.order_by("-created_at")

    # Aggregate summaries for the filtered view
    total_revenue = orders.filter(payment_status="Paid").aggregate(Sum("total"))["total__sum"] or Decimal("0.00")
    total_count = orders.count()

    return render(request, "owner/orders.html", {
        "orders": orders,
        "total_count": total_count,
        "total_revenue": total_revenue,
        "status_choices": Order.STATUS_CHOICES,
        "query": q,
        "current_status": status,
        "current_payment_status": payment_status,
        "date_from": date_from,
        "date_to": date_to,
        "current_preset": preset,
        "current_sort": sort,
    })


@owner_required
def owner_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        status = request.POST.get("status")
        payment_status = request.POST.get("payment_status")
        courier_partner = request.POST.get("courier_partner", "").strip()
        tracking_number = request.POST.get("tracking_number", "").strip()
        tracking_url = request.POST.get("tracking_url", "").strip()

        old_status = order.status
        if status in dict(Order.STATUS_CHOICES):
            order.status = status
        if payment_status:
            order.payment_status = payment_status

        order.courier_partner = courier_partner
        order.tracking_number = tracking_number
        order.tracking_url = tracking_url

        # Stock Replenishment Logic on Cancellation
        if order.status == "cancelled" and not order.stock_restored:
            with transaction.atomic():
                for item in order.items.select_related("product"):
                    item.product.stock += item.quantity
                    item.product.save(update_fields=["stock"])
                order.stock_restored = True
                order.save()
            messages.info(request, "Order cancelled: All reserved product stocks were replenished back to inventory.")
        elif old_status == "cancelled" and order.status != "cancelled" and order.stock_restored:
            # Re-deduct stock if un-cancelling
            with transaction.atomic():
                for item in order.items.select_related("product"):
                    item.product.stock = max(0, item.product.stock - item.quantity)
                    item.product.save(update_fields=["stock"])
                order.stock_restored = False
                order.save()
            messages.info(request, "Order re-opened: Reserved product stocks deducted from inventory.")
        else:
            order.save()

        messages.success(request, "Order updated successfully.")
        return redirect("owner_order_detail", order_id=order.id)
    return render(request, "owner/order_detail.html", {"order": order})


@owner_required
def owner_order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        order_num = order.id
        # Replenish stock if order was never cancelled before deletion
        if not order.stock_restored:
            with transaction.atomic():
                for item in order.items.select_related("product"):
                    item.product.stock += item.quantity
                    item.product.save(update_fields=["stock"])
        order.delete()
        messages.success(request, f"Order #{order_num} was deleted and product inventory was safely updated.")
    return redirect("owner_orders")


@owner_required
def owner_settings(request):
    settings_obj = ShopSettings.objects.first() or ShopSettings.objects.create()
    if request.method == "POST":
        settings_obj.shop_name = request.POST.get("shop_name", settings_obj.shop_name).strip()
        settings_obj.upi_id = request.POST.get("upi_id", "").strip()
        settings_obj.upi_name = request.POST.get("upi_name", "").strip()
        settings_obj.phone = request.POST.get("phone", "").strip()
        settings_obj.save()
        messages.success(request, "Payment & store settings saved.")
        return redirect("owner_settings")
    return render(request, "owner/settings.html", {"settings_obj": settings_obj})

