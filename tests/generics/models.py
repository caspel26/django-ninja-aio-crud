from unittest import mock

from ninja import Schema
from ninja_aio.models import ModelUtil
from ninja_aio.schemas.helpers import ObjectQuerySchema, ObjectsQuerySchema, QuerySchema
from ninja_aio.types import ModelSerializerMeta
from ninja_aio.exceptions import NotFoundError, SerializeError
from django.db.models import Model
from django.test import TestCase, tag

from tests.generics.request import Request
from tests.generics.literals import NOT_FOUND


class Tests:
    @tag("model_util")
    class GenericModelUtilTestCase(TestCase):
        model: Model | ModelSerializerMeta
        schema_in: Schema
        schema_out: Schema
        schema_patch: Schema

        @classmethod
        def setUpTestData(cls):
            cls.request = Request(f"{cls.model_verbose_name_path}/")
            cls.model_util = ModelUtil(cls.model)
            cls.pk_att = cls.model._meta.pk.attname
            cls.obj = cls.model.objects.select_related().create(**cls().create_data)
            if isinstance(cls.model, ModelSerializerMeta):
                cls.schema_in = cls.model.generate_create_s()
                cls.schema_out = cls.model.generate_read_s()
                cls.schema_patch = cls.model.generate_update_s()

        @property
        def serializable_fields(self) -> list:
            """
            Returns a list of serializable fields. Should be overridden in the subclass.
            """

        @property
        def model_verbose_name_path(self) -> str:
            """
            Returns the verbose name path of the model. Should be overridden in the subclass.
            """

        @property
        def model_verbose_name_view(self) -> str:
            """
            Returns the verbose name view of the model. Should be overridden in the subclass.
            """

        @property
        def create_data(self) -> dict:
            """
            Should be implemented into the child class
            """

        @property
        def read_data(self) -> dict:
            """
            Should be implemented into the child class
            """

        @property
        def reverse_relations(self) -> list:
            """
            Should be implemented into the child class
            """
            return []

        @property
        def parsed_input_data(self) -> dict:
            """
            Should be implemented into the child class
            """

        @property
        def additional_getters(self) -> dict:
            """
            Should be implemented into the child class
            """

        @property
        def additional_filters(self) -> dict:
            """
            Should be implemented into the child class
            """

        @property
        def data_in(self):
            return self.schema_in(**self.create_data)

        @property
        def data_patch(self):
            return self.schema_patch(**self.create_data)

        def test_serializable_fields(self):
            self.assertEqual(
                self.model_util.serializable_fields, self.serializable_fields
            )

        def test_verbose_name_path_resolver(self):
            self.assertEqual(
                self.model_util.verbose_name_path_resolver(),
                self.model_verbose_name_path,
            )

        def test_verbose_name_view_resolver(self):
            self.assertEqual(
                self.model_util.verbose_name_view_resolver(),
                self.model_verbose_name_view,
            )

        async def test_get_object_not_found(self):
            with self.assertRaises(NotFoundError) as exc:
                await self.model_util.get_object(self.request.get(), 0)
            self.assertEqual(
                exc.exception.error,
                {self.model._meta.verbose_name.replace(" ", "_"): NOT_FOUND},
            )
            self.assertEqual(exc.exception.status_code, 404)

        @mock.patch(
            "ninja_aio.models.ModelSerializer.queryset_request",
            new_callable=mock.AsyncMock,
        )
        async def test_get_object(self, mock_queryset_request: mock.AsyncMock):
            mock_queryset_request.return_value = self.model.objects.select_related()
            obj = await self.model_util.get_object(self.request.get(), self.obj.pk)
            self.assertEqual(obj, self.obj)
            if isinstance(self.model, ModelSerializerMeta):
                mock_queryset_request.assert_awaited_once()
            else:
                mock_queryset_request.assert_not_awaited()

        @mock.patch(
            "ninja_aio.models.ModelSerializer.queryset_request",
            new_callable=mock.AsyncMock,
        )
        async def test_get_object_with_additional_data(
            self, mock_queryset_request: mock.AsyncMock
        ):
            mock_queryset_request.return_value = (
                self.model.objects.select_related().all()
            )
            obj = await self.model_util.get_object(
                self.request.get(),
                query_data=QuerySchema(
                    filters=self.additional_filters, getters=self.additional_getters
                ),
            )
            _obj = (
                await self.model.objects.select_related()
                .filter(**self.additional_filters)
                .aget(**self.additional_getters)
            )
            self.assertEqual(obj, _obj)
            if isinstance(self.model, ModelSerializerMeta):
                mock_queryset_request.assert_awaited_once()
            else:
                mock_queryset_request.assert_not_awaited()

        def test_get_reverse_relations(self):
            self.assertEqual(
                self.model_util.get_reverse_relations(), self.reverse_relations
            )

        async def test_parse_input_data(self):
            payload, customs = await self.model_util.parse_input_data(
                self.request.post(), self.data_in
            )
            self.assertEqual(payload, self.parsed_input_data.get("payload", {}))
            self.assertEqual(customs, self.parsed_input_data.get("customs", {}))

        @mock.patch(
            "ninja_aio.models.ModelSerializer.custom_actions",
            new_callable=mock.AsyncMock,
        )
        @mock.patch(
            "ninja_aio.models.ModelSerializer.post_create",
            new_callable=mock.AsyncMock,
        )
        async def test_create_s(
            self, mock_post_create: mock.AsyncMock, mock_custom_actions: mock.AsyncMock
        ):
            mock_post_create.return_value = None
            mock_custom_actions.return_value = None
            response = await self.model_util.create_s(
                self.request.post(), self.data_in, self.schema_out
            )
            self.assertEqual(
                self.read_data | {self.pk_att: self.read_data[self.pk_att] + 1},
                response,
            )
            if isinstance(self.model, ModelSerializerMeta):
                mock_post_create.assert_awaited_once()
                mock_custom_actions.assert_awaited_once()
            else:
                mock_post_create.assert_not_awaited()
                mock_custom_actions.assert_not_awaited()

        async def test_read_s(self):
            response = await self.model_util.read_s(
                self.schema_out, self.request.get(), self.obj
            )
            self.assertEqual(response, self.read_data)

        async def test_read_s_auto_fetch(self):
            if not isinstance(self.model, ModelSerializerMeta):
                return  # focus on serializer models with schema generation
            auto = await self.model_util.read_s(
                self.schema_out,
                self.request.get(),
                instance=None,
                query_data=QuerySchema(getters={self.pk_att: self.obj.pk}),
                is_for_read=True,
            )
            self.assertEqual(auto[self.pk_att], self.obj.pk)

        async def test_read_s_missing_schema(self):
            with self.assertRaises(SerializeError):
                await self.model_util.read_s(None, self.request.get(), self.obj)

        async def test_get_object_filters_and_getters(self):
            obj = await self.model_util.get_object(
                self.request.get(),
                query_data=QuerySchema(filters={}, getters={self.pk_att: self.obj.pk}),
            )
            self.assertEqual(getattr(obj, self.pk_att), self.obj.pk)

        async def test_get_object_not_found_with_getters(self):
            with self.assertRaises(NotFoundError):
                await self.model_util.get_object(
                    self.request.get(),
                    query_data=QuerySchema(getters={self.pk_att: 999999}),
                )

        async def test_get_object_without_getters(self):
            if not isinstance(self.model, ModelSerializerMeta):
                return
            with self.assertRaises(
                ValueError,
                msg="Either pk or getters must be provided for single object retrieval.",
            ):
                await self.model_util.get_object(
                    self.request.get(),
                    query_data=QuerySchema(),
                    with_qs_request=False,
                )

        async def test_get_object_without_qs_request(self):
            if not isinstance(self.model, ModelSerializerMeta):
                return
            with mock.patch(
                "ninja_aio.models.ModelSerializer.queryset_request",
                new_callable=mock.AsyncMock,
            ) as m_qs:
                await self.model_util.get_object(
                    self.request.get(),
                    self.obj.pk,
                    query_data=QuerySchema(),
                    with_qs_request=False,
                )
                m_qs.assert_not_awaited()

        async def test_get_object_with_optimizations_union(self):
            if not isinstance(self.model, ModelSerializerMeta):
                return
            # Provide explicit lists to merge with auto-discovered ones
            query_data = ObjectQuerySchema(
                select_related=self.model_util.get_select_relateds(),
                prefetch_related=self.model_util.get_reverse_relations(),
                getters={self.pk_att: self.obj.pk},
            )
            with (
                mock.patch(
                    "django.db.models.query.QuerySet.select_related",
                    side_effect=lambda qs, *_: qs,
                    autospec=True,
                ) as m_sel,
                mock.patch(
                    "django.db.models.query.QuerySet.prefetch_related",
                    side_effect=lambda qs, *_: qs,
                    autospec=True,
                ) as m_pref,
            ):
                await self.model_util.get_object(
                    self.request.get(),
                    query_data=query_data,
                    is_for_read=True,
                )
                sel_args = m_sel.call_args[0][1:] if m_sel.call_args else []
                pref_args = m_pref.call_args[0][1:] if m_pref.call_args else []
                for rel in self.model_util.get_select_relateds():
                    self.assertIn(rel, sel_args)
                for rel in self.model_util.get_reverse_relations():
                    self.assertIn(rel, pref_args)

        async def test_update_s_object_not_found(self):
            with self.assertRaises(NotFoundError) as exc:
                await self.model_util.update_s(
                    self.request.patch(), self.data_patch, 0, self.schema_out
                )
            self.assertEqual(exc.exception.status_code, 404)
            self.assertEqual(
                exc.exception.error,
                {self.model._meta.verbose_name.replace(" ", "_"): NOT_FOUND},
            )

        async def test_update_s(self):
            response = await self.model_util.update_s(
                self.request.patch(), self.data_patch, self.obj.pk, self.schema_out
            )
            self.assertEqual(response, self.read_data)

        async def test_delete_s_object_not_found(self):
            with self.assertRaises(NotFoundError) as exc:
                await self.model_util.delete_s(self.request.delete(), 0)
            self.assertEqual(exc.exception.status_code, 404)
            self.assertEqual(
                exc.exception.error,
                {self.model._meta.verbose_name.replace(" ", "_"): NOT_FOUND},
            )

        async def test_delete_s(self):
            response = await self.model_util.delete_s(
                self.request.delete(), self.obj.pk
            )
            self.assertEqual(response, None)

        async def test_list_read_s(self):
            response = await self.model_util.list_read_s(
                self.schema_out, self.request.get(), self.model.objects.all()
            )
            self.assertEqual(response, [self.read_data])

        async def test_read_s_without_request_and_instance(self):
            with self.assertRaises(
                SerializeError,
                msg={"request": "must be provided when object is not given"},
            ):
                await self.model_util.read_s(self.schema_out, None, None)

        async def test_read_s_without_query_data_and_object(self):
            with self.assertRaises(
                SerializeError,
                msg={"query_data": "must be provided when object is not given"},
            ):
                await self.model_util.read_s(self.schema_out, self.request.get(), None)

        async def test_read_s_with_filters_and_getters(self):
            with self.assertRaises(
                SerializeError,
                msg={"query_data": "cannot contain both filters and getters"},
            ):
                await self.model_util.read_s(
                    self.schema_out,
                    self.request.get(),
                    instance=None,
                    query_data=QuerySchema(
                        filters={self.pk_att: self.obj.pk},
                        getters={self.pk_att: self.obj.pk},
                    ),
                    is_for_read=True,
                )

        async def test_list_read_s_with_filters(self):
            response = await self.model_util.list_read_s(
                self.schema_out,
                self.request.get(),
                query_data=ObjectsQuerySchema(filters={self.pk_att: self.obj.pk}),
                is_for_read=True,
            )
            self.assertEqual(response, [self.read_data])

        async def test_read_s_without_filters_and_getters(self):
            with self.assertRaises(
                SerializeError,
                msg={"query_data": "must contain either filters or getters"},
            ):
                await self.model_util.read_s(
                    self.schema_out,
                    self.request.get(),
                    query_data=ObjectsQuerySchema(),
                    is_for_read=True,
                )

        async def test_read_s_with_reverse_relations(self):
            if not self.reverse_relations:
                return  # Skip if no reverse relations defined
            response = await self.model_util.read_s(
                self.schema_out, self.request.get(), self.obj, is_for_read=True
            )
            for rel in self.reverse_relations:
                self.assertIn(rel, response)

        async def test_list_read_s_with_reverse_relations(self):
            if not self.reverse_relations:
                return  # Skip if no reverse relations defined
            response = await self.model_util.list_read_s(
                self.schema_out,
                self.request.get(),
                self.model.objects.all(),
                is_for_read=True,
            )
            for item in response:
                for rel in self.reverse_relations:
                    self.assertIn(rel, item)
