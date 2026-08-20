from django.db import models
from django.utils.text import slugify


class Genre(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Franchise(models.Model):
    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name


class Title(models.Model):
    TYPE_CHOICES = [("anime", "Anime"), ("movie", "Movie"), ("ova", "OVA"), ("special", "Special")]
    STATUS_CHOICES = [("ongoing", "Ongoing"), ("finished", "Finished"), ("planned", "Planned")]

    name = models.CharField(max_length=240)
    slug = models.SlugField(max_length=260, unique=True)
    original_name = models.CharField(max_length=240, blank=True)
    synopsis = models.TextField(blank=True)
    title_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="anime")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    poster_url = models.URLField(blank=True)
    genres = models.ManyToManyField(Genre, related_name="titles", blank=True)
    franchise = models.ForeignKey(Franchise, related_name="titles", null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["title_type"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Episode(models.Model):
    title = models.ForeignKey(Title, related_name="episodes", on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=240, blank=True)
    synopsis = models.TextField(blank=True)
    air_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["title", "number"], name="unique_title_episode_number")]

    def __str__(self) -> str:
        return f"{self.title.name} #{self.number}"


class Source(models.Model):
    KIND_CHOICES = [("sub", "Sub"), ("dub", "Dub"), ("raw", "Raw")]
    AVAILABILITY_CHOICES = [("available", "Available"), ("unavailable", "Unavailable"), ("restricted", "Restricted")]
    episode = models.ForeignKey(Episode, related_name="sources", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    url = models.URLField()
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="sub")
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default="available")
    availability_reason = models.CharField(max_length=240, blank=True)

    @property
    def is_available(self) -> bool:
        return self.availability == "available"

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["episode", "name", "kind"], name="unique_episode_source")]

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"
