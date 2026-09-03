"""Make substring search indexable.

The catalog is searched by fragment (`ILIKE '%нару%'`), which no B-tree can
serve, so every keystroke that survived debounce scanned the character table and
its 13986 translations end to end. `pg_trgm` makes a leading-wildcard match
indexable; `catalog/search.py` carries the query shape that lets the planner use
it, and neither half helps without the other.

The expression matters. Django compiles `icontains` to
``UPPER(name::text) LIKE UPPER('%…%')``, so an index on the bare column is never
consulted — verified on the production dump: with raw-column trigram indexes the
ORM query still sequentially scanned all three tables in 31ms. These indexes are
built on ``UPPER(column::text)`` to match, which takes the same query to 1.4ms.

Written as raw SQL behind a vendor guard rather than as `Meta.indexes`:
`GinIndex(OpClass(Upper(...)))` raises `OperationalError` when SQLite tries to
apply it, and the test database is SQLite. The trade-off is that these indexes do
not appear in Django's model state, so `makemigrations` cannot detect drift on
them — if you drop one, drop it here.

Index sizes on the production dump: 632 kB + 200 kB for characters, 1120 kB for
their translations, against a 2160 kB / 928 kB heap. The whole migration took
~3s. Titles and franchises are two orders of magnitude smaller today, but the
same query shape runs against them and an unindexed branch would decide the plan
once the catalog grows. Plain `CREATE INDEX` takes an ACCESS EXCLUSIVE lock,
which is acceptable at these sizes; revisit with CONCURRENTLY if a table reaches
millions of rows.

Two-character terms are not helped by these indexes: a trigram needs three
characters, so `%lu%` produces none and the planner scans. See
`catalog/search.py` for why that case is left to the response cache.
"""

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations

# (table, column, index name) — one per field reachable from catalog/search.py.
TRIGRAM_TARGETS = [
    ("catalog_title", "name", "catalog_title_name_trgm"),
    ("catalog_title", "original_name", "catalog_title_orig_trgm"),
    ("catalog_titletranslation", "name", "catalog_title_tr_trgm"),
    ("catalog_character", "name", "catalog_char_name_trgm"),
    ("catalog_character", "original_name", "catalog_char_orig_trgm"),
    ("catalog_charactertranslation", "name", "catalog_char_tr_trgm"),
    ("catalog_franchise", "name", "catalog_franchise_name_trgm"),
    ("catalog_franchisetranslation", "name", "catalog_franchise_tr_trgm"),
]


def create_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table, column, name in TRIGRAM_TARGETS:
        schema_editor.execute(
            f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" '
            f'USING gin (UPPER("{column}"::text) gin_trgm_ops)'
        )


def drop_trigram_indexes(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for _table, _column, name in TRIGRAM_TARGETS:
        schema_editor.execute(f'DROP INDEX IF EXISTS "{name}"')


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0018_performance_indexes'),
    ]

    operations = [
        TrigramExtension(),
        migrations.RunPython(create_trigram_indexes, drop_trigram_indexes),
    ]
