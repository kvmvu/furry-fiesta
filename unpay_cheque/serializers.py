from rest_framework import serializers
from .models import UnpaidCheque, Charge
from django.contrib.auth.models import User


class UnpaidChequeSerializer(serializers.HyperlinkedModelSerializer):
    raw_string = serializers.CharField(max_length=100)
    owner = serializers.ReadOnlyField(source='owner.username')
    posted_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = UnpaidCheque

        fields = ['raw_string', 'owner', 'posted_at', 'voucher_code', 'cheque_number', 'reason_code', 'cheque_amount',
                'cheque_value_date', 'ft_ref', 'logged_at', 'is_unpaid', 'unpaid_value_date', 'cc_record', 'unpay_success_indicator', 
                'unpay_error_message', 'cheque_account']
        read_only_fields = ['posted_at', 'owner', 'voucher_code', 'cheque_number', 'reason_code', 'cheque_amount', 'cheque_value_date',
                            'ft_ref', 'logged_at', 'is_unpaid', 'unpaid_value_date', 'cc_record', 'unpay_success_indicator', 'unpay_error_message',
                            'cheque_account']


class UserSerializer(serializers.HyperlinkedModelSerializer):
    unpaid_cheques = serializers.HyperlinkedRelatedField(many=True, view_name='unpaid-cheque-details', read_only=True)

    class Meta:
        model = User
        fields = ['url', 'id', 'username', 'unpaid_cheques']


class ChargeSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    cc_record = serializers.ReadOnlyField(source='cc_record.cc_record')

    class Meta:
        model = Charge
        fields = ['charge_id', 'charge_account', 'charge_amount', 'charge_value_date', 'charge_success_indicator',
                  'charge_error_message', 'owner', 'cc_record', 'ofs_id', 'ft_ref', 'is_collected']
        read_only_fields = ['charge_id', 'charge_amount', 'charge_value_date', 'charge_success_indicator', 
                            'charge_error_message', 'owner', 'cc_record', 'ofs_id', 'is_collected']