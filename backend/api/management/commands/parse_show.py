"""python manage.py parse_show <pack> [--out DIR] [--aliases FILE]

A thin wrapper: all logic lives in engine.screenplay so it also runs without Django."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from engine.screenplay.cli import run


class Command(BaseCommand):
    help = "Parse a screenplay pack (folder or .zip) into show.json, parse_report.json and episode renderings."

    def add_arguments(self, parser):
        parser.add_argument("pack")
        parser.add_argument("--out")
        parser.add_argument("--aliases")

    def handle(self, *args, **options):
        argv = [options["pack"]]
        for flag in ("out", "aliases"):
            if options[flag]:
                argv += [f"--{flag}", options[flag]]
        code = run(argv, data_dir=settings.RANGDRISHTI_DATA_DIR)
        if code == 2:
            raise CommandError("Input not found or not readable.")
        if code == 1:
            raise CommandError("Parsed with errors. See parse_report.json.")
