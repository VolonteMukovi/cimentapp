from django.conf import settings
from django.http import HttpResponse


class MaxUploadSizeMiddleware:
    """Refuse un corps trop gros avant que Django ne le lise en mémoire."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method in ("POST", "PUT", "PATCH"):
            raw = request.META.get("CONTENT_LENGTH")
            if raw:
                try:
                    length = int(raw)
                except (TypeError, ValueError):
                    length = 0
                if length > settings.MAX_UPLOAD_BYTES:
                    return HttpResponse(
                        "Fichier trop volumineux (maximum %s Mo)."
                        % (settings.MAX_UPLOAD_BYTES // (1024 * 1024)),
                        status=413,
                        content_type="text/plain; charset=utf-8",
                    )
        return self.get_response(request)
