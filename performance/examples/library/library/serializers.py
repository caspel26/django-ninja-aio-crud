from ninja_aio import Serializer, SchemaConfig

from .models import ActivityLog, Tag


class TagSerializer(Serializer[Tag]):
    """A plain Django model exposed through a Meta-driven serializer."""

    class Meta:
        model = Tag

    class Schemas:
        create = SchemaConfig(fields=["name"])
        update = SchemaConfig(optionals=[("name", str)])
        read = SchemaConfig(fields=["id", "name"])

    def post_create(self, instance):
        ActivityLog.objects.create(event="tag_created", ref=instance.pk)

    async def apost_create(self, instance):
        await ActivityLog.objects.acreate(event="tag_created", ref=instance.pk)

    def before_save(self, instance):
        instance.name = instance.name.strip().lower()
