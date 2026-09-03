"""Substring search across a model and its translation table.

The catalog is searched by fragment: a viewer types "нару" and expects Наруто,
in whichever language the row happens to be stored. That is `ILIKE '%…%'`, which
no B-tree can serve, so the tables were scanned end to end on every keystroke
that survived debounce.

Two things had to change together, and neither works alone:

1. `pg_trgm` indexes on `UPPER(column::text)` — migration ``catalog.0019``,
   which explains why the expression matters.
2. The query shape. ``Q(name__icontains=q) | Q(translations__name__icontains=q)``
   compiles to a JOIN with an OR across both tables, and Postgres cannot use a
   per-table index for that: measured on the production dump, it sequentially
   scanned all 7007 characters and 13986 translations even with the indexes
   present.

Matching ids are collected as a `UNION` of one indexed subquery per field, and
the outer query filters on `pk__in`. `UNION` rather than an OR of several
`pk__in` clauses on purpose: the OR form makes Postgres scan the outer table to
evaluate the disjunction (7007 rows removed by filter), while the union is a
single set the planner probes by primary key.

Measured on the production dump, character search with a 3+ character term:
14.3ms → 1.5ms. Scaled to 70070 characters the same query is 80ms unindexed and
10ms indexed.

**Two-character terms stay unindexed.** A trigram is three characters, so a
`%lu%` pattern yields none and the planner falls back to a scan — 83ms at 70k
rows. `GlobalSearchView.min_query_length` is 2 because two characters are a
meaningful query in Japanese, so the shortest allowed term is exactly the case
the index cannot serve. The shared response cache is what covers it; if that
becomes the bottleneck, the fix is a prefix index or a minimum of three
characters, not a different trigram configuration.

The rewrite also removes the need for `.distinct()`: `UNION` deduplicates, and
without a JOIN there is no row fan-out, so an entity with two matching
translations is returned once and the deduplicating sort disappears.
"""

from django.db.models import Model, QuerySet


def translated_name_matches(
    model: type[Model],
    translation_model: type[Model],
    query: str,
    *,
    own_fields: tuple[str, ...] = ("name",),
    translation_field: str = "name",
    translation_fk: str,
) -> QuerySet:
    """Primary keys of `model` rows matching `query` by own or translated name.

    Each branch is a separate subquery over one table, which is what keeps the
    trigram indexes usable. `order_by()` is cleared on every branch because a
    compound `UNION` rejects ordered subqueries, and these models carry a default
    ordering. `translation_fk` names the foreign key back to the parent model.
    """
    branches = [
        model._default_manager.filter(**{f"{field}__icontains": query}).order_by().values("pk")
        for field in own_fields
    ]
    branches.append(
        translation_model._default_manager.filter(**{f"{translation_field}__icontains": query})
        .order_by()
        .values(translation_fk)
    )
    first, *rest = branches
    return first.union(*rest) if rest else first


def search_titles(queryset: QuerySet, query: str) -> QuerySet:
    """Filter titles by name, original name or any translated name."""
    from .models import Title, TitleTranslation

    return queryset.filter(
        pk__in=translated_name_matches(
            Title,
            TitleTranslation,
            query,
            own_fields=("name", "original_name"),
            translation_fk="title",
        )
    )


def search_characters(queryset: QuerySet, query: str) -> QuerySet:
    """Filter characters by name, original name or any translated name."""
    from .models import Character, CharacterTranslation

    return queryset.filter(
        pk__in=translated_name_matches(
            Character,
            CharacterTranslation,
            query,
            own_fields=("name", "original_name"),
            translation_fk="character",
        )
    )


def search_franchises(queryset: QuerySet, query: str) -> QuerySet:
    """Filter franchises by name or any translated name."""
    from .models import Franchise, FranchiseTranslation

    return queryset.filter(
        pk__in=translated_name_matches(
            Franchise, FranchiseTranslation, query, translation_fk="franchise"
        )
    )
