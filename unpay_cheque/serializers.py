from rest_framework import serializers
from .models import UnpaidCheque
from django.contrib.auth.models import User


class UnpaidChequeSerializer(serializers.HyperlinkedModelSerializer):
    original_string = serializers.CharField(max_length=100)
    owner = serializers.ReadOnlyField(source='owner.username')
    posted_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = UnpaidCheque

        fields = ['original_string', 'owner', 'posted_at']


class UserSerializer(serializers.HyperlinkedModelSerializer):
    unpaid_cheques = serializers.HyperlinkedRelatedField(many=True, view_name='unpaid-cheque-details', read_only=True)

    class Meta:
        model = User
        fields = ['url', 'id', 'username', 'unpaid_cheques']