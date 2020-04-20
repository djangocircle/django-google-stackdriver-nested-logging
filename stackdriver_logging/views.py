from rest_framework.response import Response
from rest_framework.views import APIView
import logging

logger = logging.getLogger('StackDriverHandler')

class UserView(APIView):
    def get(self, request):
        logger.info("Init log from view")
        logger.warning("Warning: Init worning from view")
        logger.error("Test error")
        
        return Response("Success")