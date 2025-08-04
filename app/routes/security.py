import re

from flask import request, current_app, abort


def check_referrer():
    """
    Validate the request's Referer header to ensure it originates from an allowed domain.

    Allowed domains include:
        - Any subdomain of tamermap.com (HTTP/HTTPS)
        - Local development URLs: http://127.0.0.1:5000 and http://localhost:5000

    Aborts the request with a 403 error if the Referer is missing or unauthorized.
    """
    referer = request.headers.get("Referer", "")
    allowed_pattern = re.compile(r"^(https?://(?:.+\.)?tamermap\.com)", re.IGNORECASE)
    allowed_locals = [
        "http://127.0.0.1:5000",
        "http://localhost:5000",
        "http://127.0.0.1:5000/",
        "http://localhost:5000/",
        "http://127.0.0.1:5000/maps",
        "http://localhost:5000/maps"
    ]

    # For development, also allow empty referer
    if not referer or (
        not allowed_pattern.match(referer)
        and not any(referer.startswith(local) for local in allowed_locals)
    ):
        current_app.logger.warning(f"Unauthorized access to {request.path} from referer: {referer}")
        abort(403)
