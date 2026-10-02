from django.core.management.base import BaseCommand
from shop.models import Category, Product


class Command(BaseCommand):
    help = "Create demo categories and products."

    def handle(self, *args, **kwargs):
        data = {
            "Tops": [
                ("Soft Ribbed Tee", 799, "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?auto=format&fit=crop&w=900&q=85"),
                ("Everyday Oversized Shirt", 1299, "https://images.unsplash.com/photo-1603252110481-7ba873bf42ab?auto=format&fit=crop&w=900&q=85"),
            ],
            "Dresses": [
                ("Weekend Midi Dress", 1599, "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?auto=format&fit=crop&w=900&q=85"),
                ("City Lights Dress", 1899, "https://images.unsplash.com/photo-1539008835657-9e8e9680c956?auto=format&fit=crop&w=900&q=85"),
            ],
            "Bottoms": [
                ("Relaxed Straight Jeans", 1799, "https://images.unsplash.com/photo-1542272604-787c3835535d?auto=format&fit=crop&w=900&q=85"),
                ("Daily Wide-Leg Trousers", 1499, "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?auto=format&fit=crop&w=900&q=85"),
            ],
            "Co-ords": [
                ("Minimal Co-ord Set", 2199, "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=900&q=85"),
                ("Sunday Linen Set", 1999, "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=900&q=85"),
            ],
        }

        for category_name, products in data.items():
            category, _ = Category.objects.get_or_create(
                name=category_name,
                defaults={"slug": category_name.lower().replace(" ", "-")}
            )
            for name, price, image_url in products:
                slug = name.lower().replace(" ", "-")
                Product.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "name": name,
                        "category": category,
                        "description": "A demo product for the FOLLOW ME boutique presentation. Replace this copy with the owner's actual product details.",
                        "price": price,
                        "compare_at_price": price + 400,
                        "image_url": image_url,
                        "sizes": "S,M,L,XL",
                        "stock": 20,
                        "featured": True,
                        "is_new": True,
                    }
                )

        self.stdout.write(self.style.SUCCESS("Demo boutique data created."))
