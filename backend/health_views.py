from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """Simple health check endpoint for deployment verification"""
    return JsonResponse({
        'status': 'healthy',
        'message': 'Backend is running successfully',
        'version': '1.0.0'
    })