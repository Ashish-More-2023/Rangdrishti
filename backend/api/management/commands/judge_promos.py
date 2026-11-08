"""python manage.py judge_promos <processed show folder> [options]: thin wrapper around engine.judge.cli."""
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from engine.judge.cli import run


class Command(BaseCommand):
    help = "AI-judge the rule-based candidates; writes promos.json, promos.csv, judge_report.json."

    def add_arguments(self, parser):
        parser.add_argument("folder", nargs="?")
        for flag in ("provider", "model", "episodes", "config"):
            parser.add_argument(f"--{flag}")
        parser.add_argument("--max-calls", type=int)
        parser.add_argument("--refresh", action="store_true")
        parser.add_argument("--list-models", action="store_true")

    def handle(self, *args, **o):
        argv = [o["folder"]] if o["folder"] else []
        for flag in ("provider", "model", "episodes", "config"):
            if o[flag]:
                argv += [f"--{flag}", o[flag]]
        if o["max_calls"] is not None:
            argv += ["--max-calls", str(o["max_calls"])]
        argv += ["--refresh"] if o["refresh"] else []
        argv += ["--list-models"] if o["list_models"] else []
        code = run(argv, data_dir=settings.RANGDRISHTI_DATA_DIR)
        if code == 2:
            raise CommandError("Setup problem (see message above).")
        if code == 1:
            sys.stderr.write("Some episodes failed; outputs use rule-only fallback for them.\n")
