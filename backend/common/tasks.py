from celery import shared_task

from common import availability


@shared_task(name="common.tasks.probe_site_availability")
def probe_site_availability() -> dict[str, bool]:
    """One minute-resolution availability sample for every target."""
    outcomes = availability.probe_all()
    availability.prune()
    return outcomes
