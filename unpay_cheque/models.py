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
    unpaid_value_date = models.DateField(blank=True, null=True)
    cc_record = models.CharField(max_length=100, blank=True, null=True)
    unpay_success_indicator = models.CharField(max_length=50, blank=True, null=True)
    unpay_error_message = models.CharField(max_length=100, blank=True, null=True)
    cheque_account = models.CharField(max_length=100, blank=True, null=True)
    owner = models.ForeignKey('auth.User', related_name='unpaid_cheques', on_delete=models.CASCADE)

    def __str__(self):
        return self.ft_ref

    class Meta:
        ordering = ['logged_at']


# model to store charge details
class Charge(models.Model):
    charge_id = models.CharField(max_length=100)
    charge_account = models.CharField(max_length=100)
    charge_amount = models.DecimalField(max_digits=9, decimal_places=2)
    charge_value_date = models.DateField()
    charge_success_indicator = models.CharField(max_length=50, blank=True, null=True)
    ofs_id = models.CharField(max_length=100, blank=True, null=True)
    is_collected = models.BooleanField(default=False)
    charge_error_message = models.CharField(max_length=100, blank=True, null=True)
    cc_record = models.ForeignKey('UnpaidCheque', related_name='charges', on_delete=models.CASCADE)  
    owner = models.ForeignKey('auth.User', related_name='charges', on_delete=models.CASCADE)

    def __str__(self):
        return self.charge_id

    class Meta:
        ordering = ['charge_id']