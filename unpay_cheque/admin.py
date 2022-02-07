from django.contrib import admin
from .models import UnpaidCheque, Charge

# Register your models here.
admin.site.register(UnpaidCheque)
admin.site.register(Charge)

