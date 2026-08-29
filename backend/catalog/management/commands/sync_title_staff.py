import re
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify

from catalog.management.commands.fetch_shikimori import graphql_post
from catalog.models import Creator, Title, TitleCredit


SHIKIMORI_ID = re.compile(r"^(\d+)-")
ROLE_PRIORITY = {
    "original creator": 0,
    "original story": 1,
    "director": 10,
    "series composition": 20,
    "script": 25,
    "character design": 30,
    "music": 40,
    "sound director": 45,
    "art director": 50,
    "chief animation director": 55,
    "animation director": 60,
    "producer": 70,
    "episode director": 80,
    "storyboard": 85,
}


@dataclass(frozen=True)
class StaffCredit:
    external_id: str
    name: str
    aliases: tuple[str, ...]
    image_url: str
    role: str
    role_ru: str
    role_en: str
    priority: int


def select_staff(entries: list[dict], limit: int = 24) -> list[StaffCredit]:
    selected: list[StaffCredit] = []
    for entry in entries:
        person = entry.get("person") or {}
        pairs = [
            (str(en).strip(), str(ru).strip())
            for en, ru in zip(entry.get("rolesEn") or [], entry.get("rolesRu") or [])
            if str(en).strip().lower() in ROLE_PRIORITY
        ]
        if not pairs or not person.get("id"):
            continue
        pairs.sort(key=lambda pair: ROLE_PRIORITY[pair[0].lower()])
        primary = pairs[0][0]
        english = " · ".join(pair[0] for pair in pairs[:3])
        russian = " · ".join((pair[1] or pair[0]) for pair in pairs[:3])
        person_name = str(person.get("russian") or person.get("name") or "").strip()
        if not person_name:
            continue
        poster = person.get("poster") or {}
        selected.append(StaffCredit(
            external_id=str(person["id"]),
            name=person_name,
            aliases=tuple(filter(None, {person_name, str(person.get("name") or "").strip()})),
            image_url=str(poster.get("originalUrl") or poster.get("main2xUrl") or ""),
            role=(slugify(primary) or "staff").replace("-", "_")[:80],
            role_ru=russian[:200],
            role_en=english[:200],
            priority=ROLE_PRIORITY[primary.lower()],
        ))
    return sorted(selected, key=lambda item: (item.priority, item.name, item.external_id))[:limit]


def staff_query(ids: list[str]) -> str:
    joined = ",".join(ids)
    return (
        '{ animes(ids: "' + joined + '", limit: 50) {'
        ' id personRoles { rolesEn rolesRu person {'
        ' id name russian poster { originalUrl main2xUrl } } } } }'
    )


def creator_for(credit: StaffCredit) -> Creator:
    query = Q()
    for alias in credit.aliases:
        query |= Q(name__iexact=alias)
    creator = Creator.objects.filter(query).order_by("id").first() if query else None
    if creator is None:
        base = f"{credit.external_id}-{slugify(credit.name, allow_unicode=True)}"[:210]
        slug = base or f"person-{credit.external_id}"
        creator = Creator.objects.create(name=credit.name, slug=slug)
    changed = []
    if credit.image_url and creator.image_url != credit.image_url:
        creator.image_url = credit.image_url
        changed.append("image_url")
    if changed:
        creator.save(update_fields=changed)
    return creator


class Command(BaseCommand):
    help = "Replace coarse provider credits with exact per-title Shikimori staff roles."

    def add_arguments(self, parser):
        parser.add_argument("--title", help="Only this AniCast title slug")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        titles = list(Title.objects.order_by("id"))
        if options["title"]:
            titles = [title for title in titles if title.slug == options["title"]]
            if not titles:
                raise CommandError("title not found")
        by_external: dict[str, Title] = {}
        for title in titles:
            match = SHIKIMORI_ID.match(title.slug)
            if match:
                by_external[match.group(1)] = title
        updated = credits_count = 0
        ids = list(by_external)
        for offset in range(0, len(ids), 50):
            payload = graphql_post(staff_query(ids[offset:offset + 50]))
            for anime in (payload.get("data") or {}).get("animes") or []:
                title = by_external.get(str(anime.get("id")))
                credits = select_staff(anime.get("personRoles") or [])
                if title is None or not credits:
                    continue
                self.stdout.write(f"{title.slug}: {len(credits)} exact credits")
                if options["dry_run"]:
                    continue
                with transaction.atomic():
                    title.credits.all().delete()
                    for position, credit in enumerate(credits):
                        TitleCredit.objects.create(
                            title=title,
                            creator=creator_for(credit),
                            role=credit.role,
                            role_ru=credit.role_ru,
                            role_en=credit.role_en,
                            source="shikimori",
                            sort_order=position,
                        )
                updated += 1
                credits_count += len(credits)
        self.stdout.write(self.style.SUCCESS(f"updated {updated} titles, {credits_count} exact credits"))
