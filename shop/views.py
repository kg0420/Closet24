from decimal import Decimal
import urllib.parse
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

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
        products = products.filter(Q(name__icontains=q) |
Q(description__icontains=q))
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
    total_tax = Decimal("0")

    for key, item in cart_data.items():
        product = Product.objects.filter(id=item["product_id"]).first()
        if not product:
            continue
        item_subtotal = product.price * item["quantity"]
        item_tax = (item_subtotal * (product.gst_rate /Decimal("100"))).quantize(Decimal("0.01"))

        subtotal += item_subtotal
        total_tax += item_tax

        items.append({
            "key": key,
            "product": product,
            "size": item.get("size", ""),
            "quantity": item["quantity"],
            "subtotal": item_subtotal,
            "gst_rate": product.gst_rate,
            "gst_amount": item_tax,
            "item_total": item_subtotal + item_tax,
        })

    grand_total = subtotal + total_tax
    return render(request, "cart.html", {
        "items": items,
        "subtotal": subtotal,
        "total_tax": total_tax,
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


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.create(user=user, role="customer")
            login(request, user)
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "auth/register.html", {"form": form})


def login_view(request):
    from django.contrib.auth import authenticate
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username,
password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get("next", "home"))
        messages.error(request, "Invalid username or password.")
    return render(request, "auth/login.html")


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
    total_tax = Decimal("0")

    for key, item in cart_data.items():
        product = get_object_or_404(Product, id=item["product_id"])
        item_sub = product.price * item["quantity"]
        item_tax = (item_sub * (product.gst_rate / Decimal("100"))).quantize(Decimal("0.01"))
        subtotal += item_sub
        total_tax += item_tax
        items.append((key, product, item, item_sub, item_tax))

    grand_total = subtotal + total_tax

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.subtotal = subtotal
            order.total_tax = total_tax
            order.total = grand_total

            # GST Splitting: Check state (e.g. Tamil Nadu or matchingowner state)
            store_state = "Tamil Nadu"  # Change to your businesshome state
            if order.state.strip().lower() == store_state.lower():
                order.cgst = (total_tax / Decimal("2")).quantize(Decimal("0.01"))
                order.sgst = (total_tax - order.cgst).quantize(Decimal("0.01"))
                order.igst = Decimal("0.00")
            else:
                order.cgst = Decimal("0.00")
                order.sgst = Decimal("0.00")
                order.igst = total_tax

            order.save()

            for key, product, item, item_sub, item_tax in items:
                if product.stock < item["quantity"]:
                    messages.error(request, f"{product.name} is nolonger available in that quantity.")
                    order.delete()
                    return redirect("cart")
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    size=item.get("size", ""),
                    quantity=item["quantity"],
                    price=product.price,
                    gst_rate=product.gst_rate,
                    gst_amount=(item_tax / item["quantity"]).quantize(Decimal("0.01")),
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
        "total_tax": total_tax,
        "total": grand_total,
    })


@login_required
def payment_page(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    settings_obj = ShopSettings.objects.first() or ShopSettings.objects.create()

    upi_id = settings_obj.upi_id or "yourboutique@upi"
    upi_name = settings_obj.upi_name or "FOLLOW ME Boutique"
    amount = f"{order.total:.2f}"
    note = f"Order #{order.id} Boutique"

    # Construct standard NPCI compliant Merchant UPI URI
    # 'mc=5691' (Men's & Women's Clothing Stores / Apparel)
    # 'mode=02' (Secure dynamic web intent)
    # 'tr' (Unique transaction reference ID)
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
        if utr:
            order.payment_reference = utr
            order.payment_status = "Submitted / Under Verification"
            order.save(update_fields=["payment_reference","payment_status"])
            messages.success(request, "Payment reference submitted! We will verify and process your order.")
            return redirect("order_success", order_id=order.id)
        else:
            messages.error(request, "Please enter the UTR or Google Pay Transaction ID.")

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
    return render(request, "owner/products.html", {
        "products": Product.objects.select_related("category").all()
    })


@owner_required
def owner_product_new(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        # Handle multiple gallery photo uploads
        for f in request.FILES.getlist("gallery_images"):
            ProductImage.objects.create(product=product, image=f)
        messages.success(request, f"Product '{product.name}' added successfully.")
        return redirect("owner_products")
    return render(request, "owner/product_form.html", {
        "form": form,
        "heading": "Add a new product",
        "button": "Save product",
    })


@owner_required
def owner_product_edit(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        # Handle additional gallery photo uploads
        for f in request.FILES.getlist("gallery_images"):
            ProductImage.objects.create(product=product, image=f)
        messages.success(request, f"Product '{product.name}' updated successfully.")
        return redirect("owner_product_edit", product_id=product.id)
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
    return render(request, "owner/orders.html", {"orders": Order.objects.all()})


@owner_required
def owner_order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        status = request.POST.get("status")
        payment_status = request.POST.get("payment_status")
        if status in dict(Order.STATUS_CHOICES):
            order.status = status
        if payment_status:
            order.payment_status = payment_status
        order.save()
        messages.success(request, "Order updated successfully.")
        return redirect("owner_order_detail", order_id=order.id)
    return render(request, "owner/order_detail.html", {"order": order})


@owner_required
def owner_order_delete(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if request.method == "POST":
        order_num = order.id
        order.delete()
        messages.success(request, f"Order #{order_num} was deleted successfully.")
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

