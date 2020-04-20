from google.cloud.logging.resource import Resource
from google.cloud import logging as gcp_logging
from django.utils.deprecation import MiddlewareMixin
import io
import logging
import json
import threading
import time

_thread_locals = threading.local()
json_credentials_path='service-account.json'

client = gcp_logging.Client.from_service_account_json(json_credentials_path)
client.setup_logging()

client_email = ""
with io.open(json_credentials_path, "r", encoding="utf-8") as file:
    credentials_info = json.load(file)
    client_email = credentials_info["client_email"]

_LOG_RESOURCE = Resource(
    type='service_account', 
    labels={
        "email_id":  client_email,
        "project_id":  client.project
    }
)

parent_logger = client.logger("parent")

def get_current_request():
    return getattr(_thread_locals, 'request', None)

class StackDriverHandler(logging.Handler):

    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        """Add record to cloud"""
        record.request = get_current_request()
        self.logger = client.logger('stackdriver.googleapis.com%2Fapp')
        self.log_msg = self.format(record)

        TRACE = "projects/{}/traces/{}".format(client.project, threading.current_thread().ident)
        self.logger.log_text(self.log_msg, severity=record.levelname, trace=TRACE, resource=_LOG_RESOURCE)

class LoggingMiddleware(MiddlewareMixin):
    """
    Provides full logging of requests and responses
    """
    _initial_http_body = None

    def process_request(self, request):
        _thread_locals.request = request
        request_start_time = time.time()
        request_time = "%.5fs" % (time.time() - request_start_time)
        request.META['HTTP_X_UPSTREAM_SERVICE_TIME'] = request_time
        self._initial_http_body = request.body

    def process_response(self, request, response):
        """
        Adding request and response logging
        """
        request_time = request.META['HTTP_X_UPSTREAM_SERVICE_TIME']
        
        TEXT = u'TEXT'
        SEVERITY = 'INFO'
        TRACE = "projects/{}/traces/{}".format(client.project, threading.current_thread().ident)
        content_length = len(response.content)
        REQUEST = {
            'requestMethod': request.method,
            'requestUrl': request.get_full_path(),
            'status': response.status_code,
            'userAgent': request.META['HTTP_USER_AGENT'],
            'responseSize': content_length,
            'latency': request_time,
            'remoteIp': request.META['REMOTE_ADDR']
        }

        parent_logger.name = "stackdriver.googleapis.com%2Fnginx.request"
        parent_logger.log_struct({}, client=client, severity=SEVERITY, http_request=REQUEST, trace=TRACE, resource=_LOG_RESOURCE)
        return response