from rest_framework import status as http
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .health import build_health_report, database_is_available
from .responses import error, success


@api_view(["GET"])
def health(request: Request) -> Response:
    database_ok = database_is_available()
    report = build_health_report(database_ok)
    if not database_ok:
        return error(
            "service_unavailable",
            "The backend is running but cannot reach its database.",
            http.HTTP_503_SERVICE_UNAVAILABLE,
            details=report,
        )
    return success(report)


@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
def not_found(request: Request) -> Response:
    # Catch-all so unknown /api/ routes return JSON even when DEBUG=True.
    return error("not_found", f"No API endpoint at {request.path}.", http.HTTP_404_NOT_FOUND)


# ---- Results (read-only; the pipeline itself runs from the command line) ----------
from django.conf import settings  # noqa: E402
from django.http import FileResponse  # noqa: E402

from engine.results import ResultNotFound, clip_detail, csv_path, list_shows, show_results  # noqa: E402


def _missing(exc: ResultNotFound) -> Response:
    status = http.HTTP_400_BAD_REQUEST if exc.code.startswith("invalid") else http.HTTP_404_NOT_FOUND
    return error(exc.code, exc.message, status)


@api_view(["GET"])
def shows(request: Request) -> Response:
    return success({"shows": list_shows(settings.RANGDRISHTI_DATA_DIR)})


@api_view(["GET"])
def show_promos(request: Request, slug: str) -> Response:
    try:
        return success(show_results(settings.RANGDRISHTI_DATA_DIR, slug))
    except ResultNotFound as exc:
        return _missing(exc)


@api_view(["GET"])
def promo_clip(request: Request, slug: str, promo_id: str) -> Response:
    try:
        return success(clip_detail(settings.RANGDRISHTI_DATA_DIR, slug, promo_id))
    except ResultNotFound as exc:
        return _missing(exc)


@api_view(["GET"])
def promos_csv(request: Request, slug: str):
    try:
        path = csv_path(settings.RANGDRISHTI_DATA_DIR, slug)
    except ResultNotFound as exc:
        return _missing(exc)
    return FileResponse(path.open("rb"), as_attachment=True, filename=f"{slug}-promos.csv", content_type="text/csv")
