from .models import ShopSettings, Profile

def cart_count(request):
    cart = request.session.get("cart", {})
    return {"cart_count": sum(item.get("quantity", 0) for item in cart.values())}

def shop_settings(request):
    return {"shop_settings": ShopSettings.objects.first()}

def is_owner_check(request):
    if not request.user.is_authenticated:
        return {"is_owner": False,
                "is_staff_member":False,
                "is_store_admin":False,
                "user_role":"guest"
                }
    profile = Profile.objects.filter(user=request.user).first()
    if profile:
        role = profile.role
    elif request.user.is_superuser:
        role = "owner"
    elif request.user.is_staff:
        role = "staff"
    else:
        role = "customer"

    is_own = (role == "owner") or request.user.is_superuser
    is_stff = (role == "staff") 

 
    
    return {"is_owner": is_own,
            "is_staff_member":is_stff,
            "is_store_admin":is_own or is_stff,
            "user_role":role}