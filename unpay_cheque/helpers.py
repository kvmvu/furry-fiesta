# this contains helper functions for the views
import os
import logging

from datetime import datetime
from zeep import Client
from dotenv import load_dotenv
from pathlib import Path
from rest_framework import status
from rest_framework.response import Response
from .models import Charge

# define environment variables
load_dotenv()
dotenv_path = Path('test.env')

tws_user = os.getenv('TWS_USER')
tws_password = os.getenv('TWS_PWD')
tws_co_code = os.getenv('TWS_CO')
test_unpay_cheque_ws = os.getenv('TEST_UNPAY_CHEQUE_URL')
test_query_cc_ws = os.getenv('TEST_QUERY_CC_URL')
test_unpaid_charge_ws = os.getenv('TEST_CHARGE_UNPAID_URL')

# define the current date
current_date = datetime.now().strftime('%Y-%m-%d')

# define zeep client wsdls
wsdls = {
    'unpay_cheque': test_unpay_cheque_ws,
    'query_cc': test_query_cc_ws,
    'unpaid_charge': test_unpaid_charge_ws
}

class Helpers:
    # helper method to create a log file
    def setup_logger(self, name, log_file, level=logging.INFO):
        """
        - define a formatter for the log file
        - define path to log file
        - create a log directory if it does not exist
        - create a handler for the log file
        - create a logger
        - add the handler to the logger
        - return the logger
        """
        # logging formatters
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # log path
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), f'logs/{current_date}')

        # create log directory if not exists
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # create handlers
        handler = logging.FileHandler(log_file)        
        handler.setFormatter(formatter)

        # create logger
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)

        # return the logger
        return logger


    # helper method to break down string request to dictionary
    def string_to_dict(self, request):
        """
        - convert string to dictionary
        - log the string request and formatted dictionary
        - return the dictionary
        """
        request_string = request.data['raw_string']
        request_string_list = request_string.split('-')
        voucher_code = request_string_list[0]
        cheque_number = request_string_list[1]
        reason_code = request_string_list[2]
        cheque_amount = request_string_list[3]
        cheque_value_date = datetime.strptime(request_string_list[4], '%Y%m%d').strftime('%Y-%m-%d')
        ft_ref = request_string_list[5]

        # create dictionary
        request_dict = {
            'raw_string': request_string,
            'voucher_code': voucher_code,
            'cheque_number': cheque_number,
            'reason_code': reason_code,
            'cheque_amount': cheque_amount,
            'cheque_value_date': cheque_value_date,
            'ft_ref': ft_ref
        }

        # log the raw incoming request as well as the formatted request to incoming log file at INFO level
        logger = self.setup_logger('incoming', f'logs/{current_date}/incoming_requests.log')
        logger.info('raw request: ' + request_string)
        logger.info('formatted request: ' + str(request_dict))

        return request_dict


    # helper method to validate the input
    def validate_input(self, request_dict):
        """
        Given a formatted dictionary, validate the input
        - check if the voucher code is valid
        - check if the cheque number is valid
        - check if the reason code is valid
        - check if the cheque amount is valid
        - check if the cheque value date is valid
        - check if the ft_ref is valid
        - return the validated dictionary
        """
        logger = self.setup_logger('request_validation', f'logs/{current_date}/request_errors.log')
        # validate the voucher_code
        if request_dict['voucher_code'] != '09':
            # log the error and return the error message
            logger.error('Invalid voucher code')
            return {'error': 'Invalid voucher code'}

        # validate the cheque_number to not be empty
        if request_dict['cheque_number'] == '':
            # log the error and return the error message
            logger.error('Invalid cheque number')
            return {'error': 'Invalid cheque number'}

        # validate the reason_code to not be empty
        if request_dict['reason_code'] == '':
            # log the error and return the error message
            logger.error('Invalid reason code')
            return {'error': 'Invalid reason code'}

        # validate the cheque_amount to be a number with 2 decimal places and not be empty
        if request_dict['cheque_amount'] == '' or request_dict['cheque_amount'].replace('.', '', 1).isdigit() == False:
            # log the error and return the error message
            logger.error('Invalid cheque amount')
            return {'error': 'Invalid cheque amount'}

        # validate the cheque_value_date string in the format YYYYMMDD can be converted to a date
        if request_dict['cheque_value_date'] == '' or datetime.strptime(request_dict['cheque_value_date'], '%Y-%m-%d') == False:
            # log the error and return the error message
            logger.error('Invalid cheque value date')
            return {'error': 'Invalid cheque value date'}

        # validate the ft_ref
        if request_dict['ft_ref'][0:2] != 'FT':
            # log the error and return the error message
            logger.error('Invalid FT reference')
            return {'error': 'Invalid FT reference'}

        # if all the input is valid, return the validated input
        return request_dict


    # when our API is called, we have to first query a web service that gives us the CC record to unpay in T24.
    # we use the zeep library to make the call to the query_cc web service to get the CC record.
    def create_query_soap_request(self, request_dict):
        """
        - create a zeep client to query the CC record from the query_cc web service
        - define the parameters to be sent to the web service
        - make the call to the web service
        - log the response from the web service
        - return the response from the web service
        """
        logger = self.setup_logger('query_CC', f'logs/{current_date}/t24_cc_query_info.log')
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
            # log the CC ID, FT ref, account number in one line and return the response
            logger.info('CC ID - ' + response['CBLCHQCOLType'][0]['gCBLCHQCOLDetailType']['mCBLCHQCOLDetailType'][0]['ID'] + 
                        ', FT ref - ' + response['CBLCHQCOLType'][0]['gCBLCHQCOLDetailType']['mCBLCHQCOLDetailType'][0]['TXNID'] + 
                        ', account number - ' + response['CBLCHQCOLType'][0]['gCBLCHQCOLDetailType']['mCBLCHQCOLDetailType'][0]['CREDITACCNO'])
            return response
        except Exception as e:
            # log the T24 error if any else log the error
            if response['Status']['messages']:
                logger.error('T24 error: ' + response['Status']['messages'][0])
            else:
                logger.error(e)
            # return the error message
            return {'error': 'error calling T24 CC query web service'}


    # helper method to call the unpay_cheque web service given the response from the query_cc web service
    def create_unpay_soap_request(self, response):
        """
        Given the response from the query_cc web service: 
        - create a zeep client to call the unpay_cheque web service
        - define the parameters to be sent to the web service
        - make the call to the web service
        - log the response from the web service
        - return the response from the web service
        """
        # create a logger object
        logger = self.setup_logger('unpay_cheque', f'logs/{current_date}/t24_unpay_info.log')

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
            logger.info('successIndicator - ' + response['Status']['successIndicator'] +
                        ', cc_id - ' + response['Status']['transactionId'] +
                        ', ofs_id - ' + response['Status']['messageId'] +
                        ', ft_ref - ' + response['CHEQUECOLLECTIONType']['TXNID'] +
                        ', cheque_status - ' + response['CHEQUECOLLECTIONType']['CHQSTATUS'])
            # return the response
            return response
        except Exception as e:
            # log the T24 error (if any) else log the error
            if response['Status']['messages']:
                logger.error('T24 error: ' + response['Status']['messages'][0])
            else:
                logger.error(e)
            # return the error message
            return {'error': 'error calling T24 unpay web service'}


    # helper method to evaluate the response from the SOAP request.
    def evaluate_soap_response(self, request_dict, response):
        """
        this function takes the initial request_dict and the response from the unpay_cheque web service.
        - read the success indicator from the response
        - check if there is an error in the response
        - if success indicator is 'Success', update request_dict with is_unpaid, marked_unpaid_at, 
        cc_record, success_indicator, error_message as none and the owner of the request
        - if the success indicator is not 'Success', update request_dict with is_unpaid as False, 
        marked_unpaid_at as None, cc_record as None, success_indicator as the success indicator, 
        error_message as the error message and the owner of the request
        - log the error message if any
        - return the request_dict
        """
        
        # create a logger object
        logger = self.setup_logger('eval_response', f'logs/{current_date}/t24_unpay_info.log')

        # get the successIndicator and error message (if any) from the response in a try block 
        # because the response may not have the successIndicator tag
        success_indicator = response['Status']['successIndicator']
        # if the successIndicator is 'Success', then there might be no error message. So we need to 
        # check if there is an error message tag
        try:
            messages = response['Status']['messages'][0]
        except:
            messages = None
        

        # update request_dict with the is_unpaid field, marked_unpaid_at, cc_record fields
        if success_indicator == 'Success':
            request_dict['is_unpaid'] = True
            request_dict['unpaid_value_date'] = datetime.strptime(response['CHEQUECOLLECTIONType']['gDATETIME']['DATETIME'][0], '%y%m%d%H%M').strftime('%Y-%m-%d')
            request_dict['cc_record'] = response['Status']['transactionId']
            request_dict['unpay_success_indicator'] = success_indicator
            request_dict['unpay_error_message'] = ''
            request_dict['cheque_account'] = response['CHEQUECOLLECTIONType']['gCREDITACCNO']['mCREDITACCNO'][0]['CREDITACCNO']
        else:
            request_dict['is_unpaid'] = False
            request_dict['unpaid_value_date'] = None
            request_dict['cc_record'] = ''
            request_dict['unpay_success_indicator'] = success_indicator
            request_dict['unpay_error_message'] = messages

            # log the error from the web service
            logger.error(messages)

        # return the updated request_dict
        return request_dict


    # helper method to validate that charge has not been collected already for inputted cc_record
    def validate_charge_not_collected(self, request):
        """
        this function takes the request object and checks if the charge has already been collected.
        - if the charge has already been collected, return an error response
        - if the charge has not been collected, return None
        """
        # create a logger object
        logger = self.setup_logger('api_response', f'logs/{current_date}/API_response.log')

        # check if there is a cc_record that matches the inputted charge_account and see if is_collected is True
        # if there is a match, return an error response
        if Charge.objects.filter(charge_account=request.data['charge_account'], is_collected=True).exists():
            logger.error('charge has already been collected for cc_record: ' + Charge.objects.get(charge_account=request['charge_account'], is_collected=True).cc_record)
            return {'error': 'charge has already been collected'}
        # # check if the charge has already been collected
        # try:
        #     charge = Charge.objects.get(charge_account=request.data['charge_account'])
        #     if charge.is_collected:
        #         # log the error from the web service
        #         logger.error('charge already collected for cc_record: ' + request.data['cc_record'])
        #         return Response({'error': 'charge has already been collected'}, status=status.HTTP_400_BAD_REQUEST)
        # except Charge.DoesNotExist:
        #     pass
        # return None


    # helper method to send a charge request to the unpaid_charge web service
    def create_charge_soap_request(self, request):
        """
        this function takes the request object.
        - create a client object for the unpaid_charge web service
        - create a dictionary to hold the request parameters
        - call the web service in a try block
        - format the response from the web service to a dictionary and return it"""
        # create a logger object
        logger = self.setup_logger('charge_soap_request', f'logs/{current_date}/t24_charge_info.log')

        # create a client object
        client = Client(wsdls['unpaid_charge'])

        # create a dictionary to hold the request parameters
        request_parameters = {
            'WebRequestCommon': {
                'company': tws_co_code, # env variable
                'password': tws_password,  # env variable
                'userName': tws_user, # env variable
            },
            'OfsFunction': {
                'gtsControl': 0
            },
            'ACCHARGEREQUESTINUNPAIDType': {
                'DEBITACCOUNT': request.data['charge_account'],
                'CHARGEDETAIL': 'BENONLY', 
            }
        }

        # call the web service in a try block
        try:
            response = client.service.InputUnpaidCharge(**request_parameters)
            # create a response dictionary
            response_dict = {
                'charge_success_indicator': response['Status']['successIndicator'],
                'charge_id': response['Status']['transactionId'],
                'ofs_id': response['Status']['messageId'],
                'charge_account': response['ACCHARGEREQUESTType']['DEBITACCOUNT'],
                'charge_amount': response['ACCHARGEREQUESTType']['TOTALCHGAMT'],
                'charge_value_date': datetime.strptime(response['ACCHARGEREQUESTType']['gDATETIME']['DATETIME'][0], '%y%m%d%H%M').strftime('%Y-%m-%d'),
            }

            # log the successIndicator, transactionId, messageId, DEBITACCOUNT in one line and return the response
            logger.info(response_dict)
            # return a response dictionary that we'll use to create the Charge object
            return response_dict
        except Exception as e:
            # log the T24 error if any else log the error
            if response['Status']['messages']:
                logger.error('T24 error: ' + response['Status']['messages'][0])
            else:
                logger.error(e)
            # return the error message
            return {'error': 'error calling T24 charge web service'}