from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Category, Order, Product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name", "slug")
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Traditional Wear, Western Tops"}),
            "slug": forms.TextInput(attrs={"placeholder": "Optional — automatically generated if left blank"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ("full_name", "phone", "address", "city", "state",
"pincode")
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "name",
            "category",
            "description",
            "price",
            "compare_at_price",
            "gst_rate",
            "image",
            "image_url",
            "sizes",
            "stock",
            "featured",
            "is_new",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "image": forms.FileInput(attrs={
                "class": "w-full border border-white/15 rounded-2xl p-3 text-xs bg-[#161c2d] text-slate-300 focus:outline-none focus:border-red-500",
                "accept": "image/*",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "gst_rate" in self.fields:
            self.fields["gst_rate"].required = False
        if "image" in self.fields:
            self.fields["image"].required = False
        if "image_url" in self.fields:
            self.fields["image_url"].required = False