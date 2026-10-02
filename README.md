# FOLLOW ME Boutique — Django + Tailwind starter

A premium casual-fashion storefront concept designed as a client demo.

## Features

- Public storefront / landing page
- Product catalog, search, categories and sorting
- Product detail pages
- Session-based shopping bag
- Customer registration/login
- Checkout and order creation
- Customer order history
- Owner dashboard
- Django admin for products, categories, users and orders
- Product image uploads OR external image URLs
- Mobile responsive Tailwind UI

## Run locally

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open:
- Storefront: http://127.0.0.1:8000/
- Django admin: http://127.0.0.1:8000/admin/
- Owner dashboard: http://127.0.0.1:8000/owner/dashboard/

## Important demo setup

Create the owner using `createsuperuser`. A Django superuser automatically has access to `/owner/dashboard/`.

For normal customers, use `/register/`.

## Product images

You can upload images from Django admin, or paste an image URL into `image_url`.

## Production next steps

1. Move SECRET_KEY to environment variables.
2. Set DEBUG=False.
3. Configure PostgreSQL.
4. Replace Tailwind CDN with a compiled Tailwind build.
5. Add Razorpay/Stripe for real payments.
6. Add Cloudinary/S3 for product images.
7. Add WhatsApp order integration.
8. Add email/SMS order notifications.
9. Add shipping/return policy pages.
10. Deploy Django using Gunicorn + Nginx/Render/Railway/AWS.


## Owner-friendly dashboard

The owner can use `/owner/dashboard/` without technical knowledge:
- Dashboard overview
- Add/edit products
- Update price and stock
- View orders
- Update order status
- Configure Google Pay / UPI details
- View the public website

## Google Pay / UPI

This demo intentionally does not integrate Razorpay or another payment gateway. Customers can pay directly to the shop's UPI ID using Google Pay or another UPI app. The owner verifies the payment in the business's own bank/UPI app before dispatching.

This avoids gateway integration costs, but the final production setup should still follow the business's bank/UPI provider terms and limits.
