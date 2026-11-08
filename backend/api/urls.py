from django.urls import path, re_path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("shows/", views.shows, name="shows"),
    path("shows/<str:slug>/promos/", views.show_promos, name="show-promos"),
    path("shows/<str:slug>/promos.csv", views.promos_csv, name="promos-csv"),
    path("shows/<str:slug>/promos/<str:promo_id>/", views.promo_clip, name="promo-clip"),
    re_path(r"^.*$", views.not_found, name="not-found"),  # must stay last
]
