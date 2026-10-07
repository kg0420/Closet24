from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from shop.models import Order


class Command(BaseCommand):
    help = "Automatically cancel unpaid abandoned orders older than specified hours (default: 48) and restore product stock."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=48,
            help="Threshold in hours for abandoned orders (default: 48)",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        cutoff = timezone.now() - timedelta(hours=hours)

        abandoned_orders = Order.objects.filter(
            status="placed",
            payment_status__in=["Pending", "Failed"],
            payment_reference="",
            created_at__lt=cutoff,
            stock_restored=False,
        )

        count = abandoned_orders.count()
        if not count:
            self.stdout.write(self.style.SUCCESS(f"No abandoned orders older than {hours} hours found."))
            return

        restored_items_count = 0
        from shop.models import ProductSizeVariant
        with transaction.atomic():
            for order in abandoned_orders:
                for item in order.items.select_related("product"):
                    if item.size:
                        var = ProductSizeVariant.objects.filter(product=item.product, size=item.size).first()
                        if var:
                            var.stock += item.quantity
                            var.save(update_fields=["stock"])
                    item.product.stock += item.quantity
                    item.product.save(update_fields=["stock"])
                    restored_items_count += item.quantity
                order.status = "cancelled"
                order.stock_restored = True
                order.save(update_fields=["status", "stock_restored"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully cancelled {count} abandoned order(s) and restored {restored_items_count} item(s) to stock."
            )
        )
