from catalog.management.commands.fetch_shikimori import Command as ProviderCommand


class Command(ProviderCommand):
    help = "Fetch catalog metadata and emit an import_catalog JSON payload."
