"""python manage.py find_candidates <show.json | folder> [--config FILE] [--out DIR] [--gold FILE]

A thin wrapper: all logic lives in engine.candidates so it also runs without Django."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from engine.candidates.cli import run


class Command(BaseCommand):
    help = "Find rule-based promo candidates in a parsed show (writes candidates.json, candidates_report.json, candidates_review.md)."

    def add_arguments(self, parser):
        parser.add_argument("show")
        for flag in ("config", "out", "gold"):
            parser.add_argument(f"--{flag}")

    def handle(self, *args, **options):
        argv = [options["show"]]
        for flag in ("config", "out", "gold"):
            if options[flag]:
                argv += [f"--{flag}", options[flag]]
        code = run(argv, data_dir=settings.RANGDRISHTI_DATA_DIR)
        if code == 2:
            raise CommandError("Input or config problem (see message above).")
        if code == 1:
            raise CommandError("Some windows or candidates failed hard-rule validation. See candidates_report.json.")
