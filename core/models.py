from django.db import models


class LookupModel(models.Model):
    """
    Shared shape for Branch and Category (spec §3.1): a table, not an enum,
    so a fifth branch or ninth category is a row insert through Django Admin
    instead of a code change, migration, and deploy.
    """

    name_he = models.CharField(max_length=60, unique=True)
    name_en = models.CharField(max_length=60)
    sort_order = models.SmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["sort_order", "name_he"]

    def __str__(self):
        return self.name_he


class Branch(LookupModel):
    pass


class Category(LookupModel):
    pass
