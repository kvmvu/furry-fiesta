from rest_framework import serializers
from .models import UnpaidCheque, Charge
from django.contrib.auth.models import User


class UnpaidChequeSerializer(serializers.HyperlinkedModelSerializer):
    raw_string = serializers.CharField(max_length=100)
    owner = serializers.ReadOnlyField(source='owner.username')
    posted_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = UnpaidCheque

        fields = ['raw_string', 'owner', 'posted_at']


class UserSerializer(serializers.HyperlinkedModelSerializer):
    unpaid_cheques = serializers.HyperlinkedRelatedField(many=True, view_name='unpaid-cheque-details', read_only=True)

    class Meta:
        model = User
        fields = ['url', 'id', 'username', 'unpaid_cheques']


class ChargeSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    cc_record = serializers.HyperlinkedRelatedField(view_name='unpaid-cheque-details', read_only=True)

    class Meta:
        model = Charge
        fields = ['charge_id', 'charge_account', 'charge_amount', 'charge_value_date', 'charge_success_indicator',
                  'charge_error_message', 'owner', 'cc_record']
        read_only_fields = ['charge_id', 'charge_amount', 'charge_value_date', 'charge_success_indicator', 
                            'charge_error_message', 'owner', 'cc_record']