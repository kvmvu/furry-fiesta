from datetime import datetime
from .models import UnpaidCheque, Charge
from .serializers import UnpaidChequeSerializer, UserSerializer, ChargeSerializer
from .permissions import IsOwnerOrReadOnly
from .helpers import Helpers
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async


current_date = datetime.now().strftime('%Y-%m-%d')

# object of the Helper class
helper = Helpers()

# entry point for the API
@sync_to_async
@api_view(['GET'])
def api_root(request, format=None):
    return Response({
        'users': reverse('user-list', request=request, format=format),
        'unpaids': reverse('unpaid-cheques-list', request=request, format=format),
        'charges': reverse('charge-list', request=request, format=format)
    })


class UnpaidViewSet(viewsets.ModelViewSet):
    """
    This viewset automatically provides `list`, `create`, `retrieve`,
    `update` and `destroy` actions.
    """
    queryset = UnpaidCheque.objects.all()
    serializer_class = UnpaidChequeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrReadOnly]
    

    def create(self, request, *args, **kwargs):
        """
        receives a request and calls helper methods from helpers.py to: 
        - convert request to dict, 
        - validate the dict values, 
        - call the query_cc web service,
        - call the unpay_cheque web service,
        - evaluate the response from the unpay_cheque web service,
        - use the request_dict to create an UnpaidCheque object. 
        It returns an API response based on success or failure of the request. The API response also 
        includes details of the UnpaidCheque object.
        """
        # create a logger object
        logger = helper.setup_logger('api_response', f'logs/{current_date}/API_response.log')

        # read the request dict
        request_dict = helper.string_to_dict(request)

        # validate the request
        validated_request_dict = helper.validate_input(request_dict)

        # if the request is invalid, return an error message
        if 'error' in validated_request_dict:
            return Response(validated_request_dict, status=status.HTTP_400_BAD_REQUEST)

        # call the query_cc web service
        response = helper.create_query_soap_request(validated_request_dict)

        # if the response is an error message, return an error message
        if 'error' in response:
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        # call the unpay_cheque web service
        response = helper.create_unpay_soap_request(response)

        # if the response is an error message, return an error message
        if 'error' in response:
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        # evaluate the response from the unpay_cheque web service
        validated_request_dict = helper.evaluate_soap_response(validated_request_dict, response)

        # log the validated_request_dict
        logger.info(validated_request_dict)

        # create an UnpaidCheque object from the validated_request_dict and return the API response in a try block
        try:
            # update the request_dict with the owner field
            validated_request_dict['owner'] = self.request.user
            
            # create and save the UnpaidCheque object
            unpaid_cheque = UnpaidCheque(**validated_request_dict)
            unpaid_cheque.save()

            # create a response dictionary
            response_dict = {
                'is_unpaid': unpaid_cheque.is_unpaid,
                'unpaid_value_date': datetime.strptime(unpaid_cheque.unpaid_value_date, '%Y-%m-%d').strftime('%Y/%m/%d'),
                'cc_record': unpaid_cheque.cc_record,
                'unpay_success_indicator': unpaid_cheque.unpay_success_indicator,
                'ft_ref': unpaid_cheque.ft_ref,
                'cheque_number': unpaid_cheque.cheque_number,
            }
            # return the response
            return Response(response_dict, status=status.HTTP_201_CREATED)
        except Exception as e:
            # log the error from the API response creation and return an error message 
            logger.error(e)
            return Response({'error': 'error creating object'}, status=status.HTTP_400_BAD_REQUEST)


    def list(self, request, *args, **kwargs):
        """returns a list of UnpaidCheque objects"""
        unpaid_cheques = UnpaidCheque.objects.all()
        serializer = UnpaidChequeSerializer(unpaid_cheques, many=True)
        return Response(serializer.data)


    def retrieve(self, request, pk=None, *args, **kwargs):
        """returns details of a UnpaidCheque object"""
        try:
            unpaid_cheque = UnpaidCheque.objects.get(pk=pk)
        except UnpaidCheque.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = UnpaidChequeSerializer(unpaid_cheque)
        return Response(serializer.data)


    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class ChargeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows charges to be viewed or edited.
    """
    queryset = Charge.objects.all()
    serializer_class = ChargeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly,
                          IsOwnerOrReadOnly]

    # create a charge for a given unpaid cheque object
    def create(self, request, *args, **kwargs):
        """
        - checks to see if the charge had been collected,
        - if not, creates a charge object and returns the API response
        """
        # create a logger object
        logger = helper.setup_logger('charge', f'logs/{current_date}/API_response.log')

        # validate that the charge has not already been collected
        if helper.validate_charge_not_collected(request):
            return Response(helper.validate_charge_not_collected(request), status=status.HTTP_400_BAD_REQUEST)

        # call the web service in a try block
        try:
            # call the web service
            response = helper.create_charge_soap_request(request)

            # if the response is an error message, return an error message
            if 'error' in response:
                return Response(response, status=status.HTTP_400_BAD_REQUEST)

            # create a response dictionary
            response_dict = {
                'charge_success_indicator': response['charge_success_indicator'],
                'charge_id': response['charge_id'],
                'ofs_id': response['ofs_id'],
                'charge_account': response['charge_account'],
                'cc_record': UnpaidCheque.objects.get(ft_ref=request.data['ft_ref'], cheque_account=request.data['charge_account']).cc_record,
                'charge_amount': response['charge_amount'],
            }
            # if charge_success_indicator is 'Success', update is_collected as True
            if response_dict['charge_success_indicator'] == 'Success':
                response_dict['is_collected'] = True

            # update response_dict with the owner field
            response_dict['owner'] = self.request.user

            # create and save the Charge object
            charge = Charge(**response_dict)
            charge.save()

            # return the response
            return Response(response_dict, status=status.HTTP_201_CREATED)
        except Exception as e:
            # log the error from the API response creation and return an error message 
            logger.error(e)
            return Response({'error': 'error creating object'}, status=status.HTTP_400_BAD_REQUEST)
        

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This viewset automatically provides `list` and `retrieve` actions.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer