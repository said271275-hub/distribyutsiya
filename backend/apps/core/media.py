import mimetypes

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_safe
from django.views.static import serve

from .models import StoredFile


@require_safe
def serve_media(request, path):
    """/media/... so'rovlarini avval bazadan, topilmasa diskdan beradi."""
    obj = StoredFile.objects.filter(name=path).first()
    if obj is None:
        try:
            return serve(request, path, document_root=settings.MEDIA_ROOT)
        except Http404:
            raise
    content_type = obj.content_type or mimetypes.guess_type(path)[0] or "application/octet-stream"
    response = HttpResponse(bytes(obj.content), content_type=content_type)
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    # Foydalanuvchi yuklagan SVG to'g'ridan-to'g'ri ochilganda skript ishlamasligi uchun
    response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return response
