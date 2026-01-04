from django.test import TestCase, tag
from asgiref.sync import async_to_sync
from ninja_aio import NinjaAIO
from ninja_aio.models import ModelUtil
from ninja_aio.schemas import M2MRelationSchema
from tests.generics.request import Request
from tests.test_app import models
from tests.generics.views import GenericAPIViewSet

RELATED_NAME = "test_model_serializers"


class TestM2MViewSet(GenericAPIViewSet):
    model = models.TestModelSerializerManyToMany
    m2m_relations = [
        M2MRelationSchema(
            model=models.TestModelSerializerReverseManyToMany,
            related_name=RELATED_NAME,
            filters={"name": (str, "")},
            append_slash=True,
        )
    ]

    def test_model_serializers_query_params_handler(self, queryset, filters):
        name_filter = filters.get("name")
        if name_filter:
            queryset = queryset.filter(name=name_filter)
        return queryset


@tag("many_to_many_api")
class ManyToManyAPITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.api = NinjaAIO(urls_namespace="m2m_test")
        cls.viewset = TestM2MViewSet(api=cls.api)
        cls.rel_util = ModelUtil(models.TestModelSerializerReverseManyToMany)
        cls.viewset.add_views_to_route()
        cls.request = Request(cls.viewset.path)
        # Create base object
        create_view = cls.viewset.create_view()
        _, content = async_to_sync(create_view)(
            cls.request.post(), cls.viewset.schema_in(name="base", description="base")
        )
        cls.base_pk = content[cls.viewset.model_util.model_pk_name]
        cls.pk_att = cls.viewset.model_util.model_pk_name
        # Create related objects
        cls.related_objs = []
        for nm in ["a", "target", "other"]:
            obj = models.TestModelSerializerReverseManyToMany.objects.create(
                name=nm, description=nm
            )
            cls.related_objs.append(obj)
        cls.related_pks = [o.pk for o in cls.related_objs]
        cls.path_schema = cls.viewset.path_schema(**{cls.pk_att: cls.base_pk})
        cls.get_view, cls.manage_view = cls._get_related_views()

    @classmethod
    def _get_related_views(cls):
        path = (
            f"{cls.viewset.path_retrieve}/{cls.rel_util.verbose_name_path_resolver()}/"
        )
        get_view, manage_view = cls.viewset.m2m_api.router.path_operations.get(
            path
        ).operations
        return get_view.view_func, manage_view.view_func

    def _manage_data(self, add=None, remove=None):
        action_schema = self.viewset.m2m_api.views_action_map[(True, True)][1]
        return action_schema(add=add or [], remove=remove or [])

    async def test_add_related(self):
        data = self._manage_data(add=self.related_pks[:2])
        content = await self.manage_view(self.request.post(), self.path_schema, data)
        self.assertEqual(content["results"]["count"], 2)
        self.assertEqual(content["errors"]["count"], 0)

    async def test_get_related(self):
        # Ensure some are added first
        await self.test_add_related()
        content = await self.get_view(request=self.request.get(), pk=self.path_schema)
        self.assertEqual(set(content.keys()), {"items", "count"})
        self.assertEqual(content["count"], 2)
        names = {item["name"] for item in content["items"]}
        self.assertEqual(names, {"a", "target"})

    async def test_get_related_with_filters(self):
        await self.test_add_related()
        filters_schema = self.viewset.m2m_api.relations_filters_schemas[
            "test_model_serializers"
        ]
        filters = filters_schema(name="target")
        content = await self.get_view(
            request=self.request.get(), pk=self.path_schema, filters=filters
        )
        self.assertEqual(content["count"], 1)
        self.assertEqual(content["items"][0]["name"], "target")

    async def test_remove_related(self):
        await self.test_add_related()
        # Remove one
        data = self._manage_data(remove=[self.related_pks[0]])
        content = await self.manage_view(self.request.post(), self.path_schema, data)
        self.assertEqual(content["results"]["count"], 1)
        self.assertEqual(content["errors"]["count"], 0)
        # Removing again same pk should yield error
        data2 = self._manage_data(remove=[self.related_pks[0]])
        content2 = await self.manage_view(self.request.post(), self.path_schema, data2)
        self.assertEqual(content2["results"]["count"], 0)
        self.assertEqual(content2["errors"]["count"], 1)

    async def test_add_existing_error(self):
        await self.test_add_related()
        # Add again -> errors
        data = self._manage_data(add=self.related_pks[:1])
        content = await self.manage_view(self.request.post(), self.path_schema, data)
        self.assertEqual(content["results"]["count"], 0)
        self.assertEqual(content["errors"]["count"], 1)
