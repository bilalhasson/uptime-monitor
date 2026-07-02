from django.conf import settings


def site(request):
    """Expose the public base URL for absolute links (e.g. OG image tags)."""
    return {"SITE_URL": settings.SITE_URL}
