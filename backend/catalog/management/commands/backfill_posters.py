from django.core.management.base import BaseCommand

from catalog import posters


class Command(BaseCommand):
    help = (
        "Mirror posters to local storage and upgrade titles to the best "
        "MyAnimeList artwork available through Jikan "
        "(dry-run by default, --apply to write). "
        "--restore-origins instead reverts poster_url to the recorded "
        "remote sources (rollback recovery)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Download artwork and write poster_url changes")
        parser.add_argument("--limit", type=int, default=0, help="Process at most N non-maximum titles")
        parser.add_argument(
            "--restore-origins", action="store_true",
            help="Revert local poster_url values to recorded remote origins instead of upgrading",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        limit = max(0, int(options["limit"]))
        if options["restore_origins"]:
            outcomes = posters.restore_origins(apply_changes=apply_changes)
        else:
            outcomes = posters.refresh_batch(limit=limit, apply_changes=apply_changes)
        counts: dict[str, int] = {}
        for result, detail in outcomes:
            counts[result] = counts.get(result, 0) + 1
            if result == "error":
                self.stdout.write(self.style.ERROR(detail))
            elif result in ("unavailable", "invalid"):
                self.stdout.write(self.style.WARNING(detail))
            else:
                self.stdout.write(f"{result:>10} {detail}")
        breakdown = ", ".join(f"{key}: {value}" for key, value in sorted(counts.items())) or "nothing to do"
        summary = f"{len(outcomes)} processed ({breakdown})"
        if apply_changes:
            self.stdout.write(self.style.SUCCESS(f"applied: {summary}"))
        else:
            self.stdout.write(self.style.NOTICE(f"dry-run: {summary}; rerun with --apply"))
