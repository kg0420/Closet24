from .models import ShopSettings, Profile

def cart_count(request):
    cart = request.session.get("cart", {})
    return {"cart_count": sum(item.get("quantity", 0) for item in cart.values())}

def shop_settings(request):
    return {"shop_settings": ShopSettings.objects.first()}

def is_owner_check(request):
    if not request.user.is_authenticated:
        return {"is_owner": False}
    if request.user.is_staff or request.user.is_superuser:
        return {"is_owner": True}
    profile = Profile.objects.filter(user=request.user).first()
    return {"is_owner": profile is not None and profile.role == "owner"}