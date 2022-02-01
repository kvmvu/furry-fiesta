from datetime import date, datetime
from .models import UnpaidCheque
from .serializers import UnpaidChequeSerializer, UserSerializer
from .permissions import IsOwnerOrReadOnly
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse
from django.contrib.auth.models import User
from asgiref.sync import sync_to_async
from zeep import Client

import os
import logging

# logging formatters
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# setup environment variables
tws_user = os.environ.get('TWS_USER')
tws_password = os.environ.get('TWS_PWD')
tws_co_code = os.environ.get('TWS_CO')
test_unpay_cheque_ws = os.environ.get('TEST_UNPAY_CHEQUE_URL')
test_query_cc_ws = os.environ.get('TEST_QUERY_CC_URL')

# setup zeep client wsdls
wsdls = {
    'unpay_cheque': test_unpay_cheque_ws,
    'query_cc': test_query_cc_ws
}

# entry point for the API
@sync_to_async
@api_view(['GET'])
def api_root(request, format=None):
    return Response({
        'users': reverse('user-list', request=request, format=format),
        'unpaids': reverse('unpaid-cheques-list', request=request, format=format)
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

    # helper method to setup logging
    def setup_logger(self, name, log_file, level=logging.INFO):
        """To setup as many loggers as you want"""
        # log_dir = os.path.dirname(log_file)
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')

        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        handler = logging.FileHandler(log_file)        
        handler.setFormatter(formatter)

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)

        return logger


    # helper method to break down string to dictionary
    def string_to_dict(self, request):
        """
        this method converts the request to a dictionary that will be used by the other 
        methods of the class. It then logs the original request and the formatted request 
        to incoming and outgoing logs respectively.
        """
        request_string = request.data['original_string']
        request_string_list = request_string.split('-')
        voucher_code = request_string_list[0]
        cheque_number = request_string_list[1]
        reason_code = request_string_list[2]
        cheque_amount = request_string_list[3]
        cheque_value_date = datetime.strptime(request_string_list[4], '%Y%m%d').date()
        ft_ref = request_string_list[5]

        # create dictionary
        request_dict = {
            'voucher_code': voucher_code,
            'cheque_number': cheque_number,
            'reason_code': reason_code,
            'cheque_amount': cheque_amount,
            'cheque_value_date': cheque_value_date,
            'ft_ref': ft_ref
        }

        # log the raw incoming request as well as the formatted request to incoming log file at INFO level
        logger = self.setup_logger('incoming', 'logs/incoming_requests.log')
        logger.info('raw request: ' + request_string)
        logger.info('formatted request: ' + str(request_dict))

        return request_dict


    # helper method to validate the input
    def validate_input(self, request_dict):
        """
        this method validates the input from the API request. 
        It returns a dictionary with the validated input. If the input is invalid, 
        it returns an error message
        """
        logger = self.setup_logger('request_validation', 'logs/request_errors.log')
        # validate the voucher_code
        if request_dict['voucher_code'] != '09':
            # log the error and return the error message
            logger.error('Invalid voucher code')
            return {'error': 'Invalid voucher code'}

        # validate the ft_ref
        if request_dict['ft_ref'][0:2] != 'FT':
            # log the error and return the error message
            logger.error('Invalid FT reference')
            return {'error': 'Invalid FT reference'}

        # if all the input is valid, return the validated input
        return request_dict


    # when our API is called, we have to first query a web service that gives us the CC record to unpay in T24.
    # we are going to use the zeep library to make the call to the 1st web service to get the CC record and then
    # use the zeep library to make the call to the 2nd web service to unpay the cheque in T24.
    def create_query_soap_request(self, request_dict):
        """
        this method to calls the query_cc web service to get the matching CC record for the input FT ref. The CC 
        record is contained in the response. The method returns a response or an error message.
        """
        logger = self.setup_logger('query_CC', 'logs/t24_cc_query_info.log')
        # create a client object
        client = Client(wsdls['query_cc'])
        # create a dictionary to hold the request parameters
        request_parameters = {
            'WebRequestCommon': {
                'company': tws_co_code,  # env variable
                'password': tws_password, # env variable
                'userName': tws_user, # env variable
            },
            'CBLCHQCOLType': {
                'enquiryInputCollection': {
                    'columnName': 'TXN.ID',
                    'criteriaValue': request_dict['ft_ref'],
                    'operand': 'EQ'
                }
            }
        }
        # call the web service in a try block
        try:
            response = client.service.GetCCWebService(**request_parameters)
            
            # log and return the response
            if response['CBLCHQCOLType'][0]['ZERORECORDS']:
                # means that there is no record found for the given ft_ref. log this
                # message as a warning and return the error message
                logger.warning('No CC record found for ft_ref - ' + request_dict['ft_ref'])
                return {'error': 'No CC record found for ft_ref - ' + request_dict['ft_ref']}               
            # log the response
            logger.info(response)
            return response
        except Exception as e:
            # log the error
            logger.error(e)
            # return the error message
            return {'error': 'error calling T24 CC query web service'}


    # helper method to call the unpay_cheque web service once we have the CC record and CO CODE from the query web service
    def create_unpay_soap_request(self, response):
        """
        this method creates the unpay_cheque web service request. The request that is sent to the
        web service contains the CC record and the CO CODE from the query web service response. The method returns
        the response from the unpay cheque web service or an error message.
        """
        logger = self.setup_logger('unpay_cheque', 'logs/t24_unpay_info.log')
        # create a client object
        client = Client(wsdls['unpay_cheque'])
        # create a dictionary to hold the request parameters
        request_parameters = {
            'WebRequestCommon': {
                'company': response['CBLCHQCOLType'][0]['gCBLCHQCOLDetailType']['mCBLCHQCOLDetailType'][0]['COCODE'],
                'password': tws_password,  # env variable
                'userName': tws_user, # env variable
            },
            'OfsFunction': {
                'gtsControl': 0
            },
            # this tag has an attribute called 'id' which is required and it has child a child tag called 'CHQSTATUS' 
            # whose value is 'RETURNED'
            'CHEQUECOLLECTIONUNPAYType': {
                'id': response['CBLCHQCOLType'][0]['gCBLCHQCOLDetailType']['mCBLCHQCOLDetailType'][0]['ID'],
                'CHQSTATUS': 'RETURNED'
            }
        }

        # call the web service in a try block
        try:
            response = client.service.UnpayChequeWebService(**request_parameters)
            # log the response
            logger.info(response)
            # return the response
            return response
        except Exception as e:
            # log the error
            logger.error(e)
            # return the error message
            return {'error': 'error calling T24 unpay web service'}


    # helper method to evaluate the response from the SOAP request.
    def evaluate_soap_response(self, request_dict, response):
        """This method gets called if there is a response from the create_unpay_soap_request method. It receives the 
        response from the create_unpay_soap_request method and the original request_dict. It updates the request_dict 
        with details from the response and returns the updated request_dict. It checks if the successIndicator is 
        'Success' and marks is_unpaid as True. If the successIndicator is not 'Success', it logs the error message 
        and marks is_unpaid as False. It also reads the transactionId and saves it as the cc_record in the dictionary 
        to be used in the UnpayCheque object. It also marks the marked_unpaid_at as the current time."""
        
        # create a logger object
        logger = self.setup_logger('eval_response', 'logs/t24_unpay_info.log')

        # get the successIndicator and error message (if any) from the response in a try block because the response may not have the successIndicator tag
        success_indicator = response['Status']['successIndicator']
        # if the successIndicator is 'Success', then there might be no error message. So we need to check if there is an error message tag
        try:
            messages = response['Status']['messages'][0]
        except:
            messages = None
        

        # update request_dict with the is_unpaid field, marked_unpaid_at, cc_record fields
        if success_indicator == 'Success':
            request_dict['is_unpaid'] = True
            request_dict['marked_unpaid_at'] = datetime.now()
            # request_dict['marked_unpaid_at'] = str(date.today())
            request_dict['cc_record'] = response['Status']['transactionId']
            request_dict['t24_success_indicator'] = success_indicator
            request_dict['t24_error_message'] = ''
            request_dict['owner'] = self.request.user
        else:
            request_dict['is_unpaid'] = False
            request_dict['marked_unpaid_at'] = None
            request_dict['cc_record'] = ''
            request_dict['t24_success_indicator'] = success_indicator
            request_dict['t24_error_message'] = messages
            request_dict['owner'] = self.request.user

            # log the error from the web service
            logger.error(messages)

        # return the updated request_dict
        return request_dict


    def create(self, request, *args, **kwargs):
        """receives a request and calls the helper methods to: 
        - convert request to dict, 
        - validate the dict values, 
        - call the query_cc web service,
        - call the unpay_cheque web service,
        - evaluate the response from the unpay_cheque web service,
        - use the request_dict to create an UnpaidCheque object. 
        It returns an API response based on success or failure of the request. The API response also 
        includes details of the UnpaidCheque object."""
        # create a logger object
        logger = self.setup_logger('api_response', 'logs/API_response_error.log')
        # read the request
        request_dict = self.string_to_dict(request)

        # validate the request
        validated_request_dict = self.validate_input(request_dict)

        # if the request is invalid, return an error message
        if 'error' in validated_request_dict:
            return Response(validated_request_dict, status=status.HTTP_400_BAD_REQUEST)

        # call the query_cc web service
        response = self.create_query_soap_request(validated_request_dict)

        # if the response is an error message, return an error message
        if 'error' in response:
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        # call the unpay_cheque web service
        response = self.create_unpay_soap_request(response)

        # if the response is an error message, return an error message
        if 'error' in response:
            return Response(response, status=status.HTTP_400_BAD_REQUEST)

        # evaluate the response from the unpay_cheque web service
        validated_request_dict = self.evaluate_soap_response(validated_request_dict, response)
        # log the validated_request_dict
        logger.info(validated_request_dict)

        # create an UnpaidCheque object from the validated_request_dict and return the API response in a try block
        try:
            # create and save the UnpaidCheque object
            unpaid_cheque = UnpaidCheque(**validated_request_dict)
            unpaid_cheque.save()

            # create a response dictionary
            response_dict = {
                'is_unpaid': unpaid_cheque.is_unpaid,
                'marked_unpaid_at': unpaid_cheque.marked_unpaid_at,
                'cc_record': unpaid_cheque.cc_record,
                't24_success_indicator': unpaid_cheque.t24_success_indicator
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


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    This viewset automatically provides `list` and `retrieve` actions.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer