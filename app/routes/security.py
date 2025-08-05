import re

from flask import request, current_app, abort


def check_referrer():
    """
    Validate the request's Referer header to ensure it originates from an allowed domain.

    Allowed domains include:
        - Any subdomain of tamermap.com (HTTP/HTTPS)
        - Local development URLs: http://127.0.0.1:5000 and http://localhost:5000
        - Server IPs for development and production

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
    
    # Server IP patterns for development and production
    server_ip_patterns = [
        re.compile(r"^https?://137\.184\.244\.37(?::\d+)?", re.IGNORECASE),
        re.compile(r"^https?://144\.126\.210\.185(?::\d+)?", re.IGNORECASE),
        re.compile(r"^https?://144\.126\.\d+\.\d+(?::\d+)?", re.IGNORECASE),
        re.compile(r"^https?://143\.198\.\d+\.\d+(?::\d+)?", re.IGNORECASE),
        re.compile(r"^https?://134\.209\.\d+\.\d+(?::\d+)?", re.IGNORECASE),
        re.compile(r"^https?://50\.106\.23\.189(?::\d+)?", re.IGNORECASE)
    ]

    # For development, also allow empty referer
    if not referer or (
        not allowed_pattern.match(referer)
        and not any(referer.startswith(local) for local in allowed_locals)
        and not any(pattern.match(referer) for pattern in server_ip_patterns)
    ):
        current_app.logger.warning(f"Unauthorized access to {request.path} from referer: {referer}")
        abort(403)
