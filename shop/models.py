from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from django.utils.text import slugify


class Profile(models.Model):
    ROLE_CHOICES = (
        ("customer", "Customer"),
        ("owner", "Business Owner"),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="customer")

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    def save(self, *args, **kwargs):
        if self.role == "owner":
            if not self.user.is_staff or not self.user.is_superuser:
                self.user.is_staff = True
                self.user.is_superuser = True
                self.user.save(update_fields=["is_staff", "is_superuser"])
        super().save(*args, **kwargs)


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "category"
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Product(models.Model):
    GST_CHOICES = (
        (Decimal("0.00"), "0% (Exempt)"),
        (Decimal("5.00"), "5% GST (Apparel <= ₹1000)"),
        (Decimal("12.00"), "12% GST (Apparel > ₹1000)"),
        (Decimal("18.00"), "18% GST (Luxury / Accessories)"),
        (Decimal("28.00"), "28% GST"),
    )

    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Base price before GST or selling price")
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, choices=GST_CHOICES, default=Decimal("5.00"))
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    image_url = models.URLField(blank=True)
    sizes = models.CharField(max_length=120, default="S,M,L,XL")
    stock = models.PositiveIntegerField(default=0)
    featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "item"
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return int((1 - self.price / self.compare_at_price) *100)
        return 0

    @property
    def display_image(self):
        if self.image:
            return self.image.url
        if self.image_url:
            return self.image_url
        first_gallery = self.gallery_images.first()
        if first_gallery and first_gallery.image:
            return first_gallery.image.url
        return ""

    @property
    def all_images(self):
        images = []
        if self.image:
            images.append(self.image.url)
        elif self.image_url:
            images.append(self.image_url)
        for gi in self.gallery_images.all():
            if gi.image and gi.image.url not in images:
                images.append(gi.image.url)
        return images

    @property
    def gst_amount(self):
        return (self.price * (self.gst_rate / Decimal("100"))).quantize(Decimal("0.01"))

    @property
    def price_with_gst(self):
        return (self.price + self.gst_amount).quantize(Decimal("0.01"))

class ShopSettings(models.Model):
    shop_name = models.CharField(max_length=120, default="FOLLOW ME Boutique")
    phone = models.CharField(max_length=20, blank=True)
    upi_id = models.CharField(max_length=120, blank=True)
    upi_name = models.CharField(max_length=120, default="FOLLOW ME Boutique")

    def __str__(self):
        return self.shop_name


class Order(models.Model):
        STATUS_CHOICES = (
            ("placed", "Placed"),
            ("confirmed", "Confirmed"),
            ("packed", "Packed"),
            ("shipped", "Shipped"),
            ("delivered", "Delivered"),
            ("cancelled", "Cancelled"),
        )

        user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
        full_name = models.CharField(max_length=120)
        phone = models.CharField(max_length=20)
        address = models.TextField()
        city = models.CharField(max_length=80)
        state = models.CharField(max_length=80, default="Tamil Nadu")
        pincode = models.CharField(max_length=10)

        # Financial breakdown
        subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
        cgst = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
        sgst = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
        igst = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
        total_tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
        total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

        status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="placed")
        payment_method = models.CharField(max_length=50, default="Google Pay / UPI")
        payment_reference = models.CharField(max_length=100, blank=True, help_text="UPI Transaction ID / UTR")
        payment_status = models.CharField(max_length=20, default="Pending")
        created_at = models.DateTimeField(auto_now_add=True)

        class Meta:
            ordering = ["-created_at"]

        def __str__(self):
            return f"Order #{self.id} - {self.user.username}"


class OrderItem(models.Model):
        order = models.ForeignKey(Order, on_delete=models.CASCADE,related_name="items")
        product = models.ForeignKey(Product, on_delete=models.PROTECT)
        size = models.CharField(max_length=20, blank=True)
        quantity = models.PositiveIntegerField(default=1)
        price = models.DecimalField(max_digits=10, decimal_places=2)
        gst_rate = models.DecimalField(max_digits=5, decimal_places=2,default=Decimal("5.00"))
        gst_amount = models.DecimalField(max_digits=10, decimal_places=2,default=Decimal("0.00"))

        @property
        def item_subtotal(self):
            return self.price * self.quantity

        @property
        def item_total(self):
            return (self.price * self.quantity) + (self.gst_amount *self.quantity)

        def __str__(self):
            return f"{self.product.name} x {self.quantity}"

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to="products/gallery/")
    created_at = models.DateTimeField(auto_now_add=True)