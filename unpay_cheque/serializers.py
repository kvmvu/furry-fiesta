from rest_framework import serializers
from .models import UnpaidCheque
from django.contrib.auth.models import User


class UnpaidChequeSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = UnpaidCheque

        fields = ['original_string', 'owner']


class UserSerializer(serializers.HyperlinkedModelSerializer):
    unpaid_cheques = serializers.HyperlinkedRelatedField(many=True, view_name='unpaid-cheque-details', read_only=True)

    class Meta:
        model = User
        fields = ['url', 'id', 'username', 'unpaid_cheques']