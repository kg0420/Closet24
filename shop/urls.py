from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("shop/", views.shop, name="shop"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),

    path("cart/", views.cart, name="cart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<str:key>/", views.update_cart, name="update_cart"),
    path("cart/remove/<str:key>/", views.remove_from_cart, name="remove_from_cart"),

    path("register/", views.register, name="register"),
    path("register/verify-otp/", views.verify_registration_otp, name="verify_registration_otp"),
    path("register/resend-otp/", views.resend_registration_otp, name="resend_registration_otp"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("checkout/", views.checkout, name="checkout"),
    path("payment/<int:order_id>/", views.payment_page, name="payment_page"),
    path("order/success/<int:order_id>/", views.order_success, name="order_success"),
    path("orders/", views.my_orders, name="my_orders"),
    path("order/<int:order_id>/receipt/", views.download_receipt, name="download_receipt"),

    # Owner / Admin Management Routes
    path("owner/dashboard/", views.owner_dashboard, name="owner_dashboard"),
    path("owner/products/", views.owner_products, name="owner_products"),
    path("owner/products/new/", views.owner_product_new, name="owner_product_new"),
    path("owner/products/<int:product_id>/edit/", views.owner_product_edit, name="owner_product_edit"),
    path("owner/products/<int:product_id>/delete/", views.owner_product_delete, name="owner_product_delete"),
    path("owner/products/gallery-image/<int:image_id>/delete/", views.owner_product_delete_gallery_image, name="owner_product_delete_gallery_image"),

    path("owner/categories/", views.owner_categories, name="owner_categories"),
    path("owner/categories/new/", views.owner_category_new, name="owner_category_new"),
    path("owner/categories/<int:category_id>/edit/", views.owner_category_edit, name="owner_category_edit"),
    path("owner/categories/<int:category_id>/delete/", views.owner_category_delete, name="owner_category_delete"),

    path("owner/customers/", views.owner_customers, name="owner_customers"),
    path("owner/customers/<int:user_id>/toggle-role/", views.owner_customer_toggle_role, name="owner_customer_toggle_role"),

    path("owner/orders/", views.owner_orders, name="owner_orders"),
    path("owner/orders/<int:order_id>/", views.owner_order_detail, name="owner_order_detail"),
    path("owner/orders/<int:order_id>/delete/", views.owner_order_delete, name="owner_order_delete"),

    path("owner/settings/", views.owner_settings, name="owner_settings"),
]
