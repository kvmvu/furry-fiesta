from django.db import models

# model to store incoming unpaid cheque details
class UnpaidCheque(models.Model):
    raw_string = models.CharField(max_length=100)
    voucher_code = models.CharField(max_length=3)
    cheque_number = models.CharField(max_length=100)
    reason_code = models.CharField(max_length=3)
    cheque_amount = models.DecimalField(max_digits=9, decimal_places=2)
    cheque_value_date = models.DateField()
    ft_ref = models.CharField(max_length=100, blank=True, null=True)
    logged_at = models.DateTimeField(auto_now_add=True)
    is_unpaid = models.BooleanField(default=False)
    marked_unpaid_at = models.DateTimeField(blank=True, null=True)
    cc_record = models.CharField(max_length=100, blank=True, null=True)
    unpay_success_indicator = models.CharField(max_length=50, blank=True, null=True)
    unpay_error_message = models.CharField(max_length=100, blank=True, null=True)
    charge_is_paid = models.BooleanField(default=False)
    charge_paid_at = models.DateTimeField(blank=True, null=True)
    charge_id = models.CharField(max_length=100, blank=True, null=True)
    charge_account = models.CharField(max_length=100, blank=True, null=True)
    charge_success_indicator = models.CharField(max_length=50, blank=True, null=True)
    charge_error_message = models.CharField(max_length=100, blank=True, null=True)
    owner = models.ForeignKey('auth.User', related_name='unpaid_cheques', on_delete=models.CASCADE)

    def __str__(self):
        return self.ft_ref

    class Meta:
        ordering = ['logged_at']