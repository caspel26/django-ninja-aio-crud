import base64
from typing import Any

from ninja.schema import Schema
from ninja.orm import create_schema

from django.db import models
from django.http import HttpResponse, HttpRequest
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
)

from .exceptions import SerializeError
from .types import S_TYPES, REL_TYPES, ModelSerializerMeta


class ModelUtil:
    def __init__(self, model: type["ModelSerializer"] | models.Model):
        self.model = model

    @property
    def serializable_fields(self):
        if isinstance(self.model, ModelSerializerMeta):
            return self.model.ReadSerializer.fields
        return [field.name for field in self.model._meta.get_fields()]

    def verbose_name_path_resolver(self) -> str:
        return "-".join(self.model._meta.verbose_name_plural.split(" "))

    async def get_object(self, request: HttpRequest, pk: int | str):
        q = {self.model._meta.pk.attname: pk}
        obj_qs = self.model.objects.select_related()
        if isinstance(self.model, ModelSerializerMeta):
            obj_qs = await self.model.queryset_request(request)
        try:
            obj = await obj_qs.prefetch_related(*self.get_reverse_relations()).aget(**q)
        except ObjectDoesNotExist:
            raise SerializeError({self.model._meta.model_name: "not found"}, 404)
        return obj

    def get_reverse_relations(self) -> list[str]:
        reverse_rels = []
        for f in self.serializable_fields:
            field_obj = getattr(self.model, f)
            if isinstance(field_obj, ManyToManyDescriptor):
                reverse_rels.append(f)
                continue
            if isinstance(field_obj, ReverseManyToOneDescriptor):
                reverse_rels.append(field_obj.field._related_name)
                continue
            if isinstance(field_obj, ReverseOneToOneDescriptor):
                reverse_rels.append(field_obj.related.name)
        return reverse_rels

    async def parse_input_data(self, request: HttpRequest, data: Schema):
        payload = data.model_dump()
        customs = {}
        if isinstance(self.model, ModelSerializerMeta):
            customs = {k: v for k, v in payload.items() if self.model.is_custom(k)}
        for k, v in payload.items():
            if isinstance(self.model, ModelSerializerMeta) and self.model.is_custom(k):
                continue
            field_obj = getattr(self.model, k).field
            if isinstance(field_obj, models.BinaryField):
                try:
                    payload |= {k: base64.b64decode(v)}
                except Exception as exc:
                    raise SerializeError({k: ". ".join(exc.args)}, 400)
            if isinstance(field_obj, models.ForeignKey):
                rel_util = ModelUtil(field_obj.related_model)
                rel: ModelSerializer = await rel_util.get_object(request, v)
                payload |= {k: rel}
        new_payload = {k: v for k, v in payload.items() if k not in customs}
        return new_payload, customs

    async def parse_output_data(self, request: HttpRequest, data: Schema):
        olds_k: list[dict] = []
        payload = data.model_dump()
        for k, v in payload.items():
            try:
                field_obj = getattr(self.model, k).field
            except AttributeError:
                field_obj = getattr(self.model, k).related
            if isinstance(v, dict) and (
                isinstance(field_obj, models.ForeignKey)
                or isinstance(field_obj, models.OneToOneField)
            ):
                rel_util = ModelUtil(field_obj.related_model)
                rel: ModelSerializer = await rel_util.get_object(
                    request, list(v.values())[0]
                )
                if isinstance(field_obj, models.ForeignKey):
                    for rel_k, rel_v in v.items():
                        field_rel_obj = getattr(rel, rel_k)
                        if isinstance(field_rel_obj, models.ForeignKey):
                            olds_k.append({rel_k: rel_v})
                    for obj in olds_k:
                        for old_k, old_v in obj.items():
                            v.pop(old_k)
                            v |= {f"{old_k}_id": old_v}
                    olds_k = []
                payload |= {k: rel}
        return payload

    async def create_s(self, request: HttpRequest, data: Schema, obj_schema: Schema):
        try:
            payload, customs = await self.parse_input_data(request, data)
            pk = (await self.model.objects.acreate(**payload)).pk
            obj = await self.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error
        if isinstance(self.model, ModelSerializerMeta):
            await obj.custom_actions(customs)
            await obj.post_create()
        return 201, await self.read_s(request, obj, obj_schema)

    async def read_s(
        self,
        request: HttpRequest,
        obj: type["ModelSerializer"],
        obj_schema: Schema,
    ):
        if obj_schema is None:
            raise SerializeError({"obj_schema": "must be provided"}, 400)
        return await self.parse_output_data(request, obj_schema.from_orm(obj))

    async def update_s(
        self, request: HttpRequest, data: Schema, pk: int | str, obj_schema: Schema
    ):
        try:
            obj = await self.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error

        payload, customs = await self.parse_input_data(request, data)
        for k, v in payload.items():
            if v is not None:
                setattr(obj, k, v)
        if isinstance(self.model, ModelSerializerMeta):
            await obj.custom_actions(customs)
        await obj.asave()
        updated_object = await self.get_object(request, pk)
        return await self.read_s(request, updated_object, obj_schema)

    async def delete_s(self, request: HttpRequest, pk: int | str):
        try:
            obj = await self.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error
        await obj.adelete()
        return HttpResponse(status=204)


class ModelSerializer(models.Model, metaclass=ModelSerializerMeta):
    class Meta:
        abstract = True

    class CreateSerializer:
        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []

    class ReadSerializer:
        fields: list[str] = []

    class UpdateSerializer:
        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []

    @property
    def has_custom_fields_create(self):
        return hasattr(self.CreateSerializer, "customs")

    @property
    def has_custom_fields_update(self):
        return hasattr(self.UpdateSerializer, "customs")

    @property
    def has_custom_fields(self):
        return self.has_custom_fields_create or self.has_custom_fields_update

    @classmethod
    def verbose_name_path_resolver(cls) -> str:
        return "-".join(cls._meta.verbose_name_plural.split(" "))

    def has_changed(self, field: str) -> bool:
        """
        Check if a model field has changed
        """
        if not self.pk:
            return False
        old_value = (
            self.__class__._default_manager.filter(pk=self.pk)
            .values(field)
            .get()[field]
        )
        return getattr(self, field) != old_value

    @classmethod
    async def queryset_request(cls, request: HttpRequest):
        """
        Override this method to return a filtered queryset based
        on the request received
        """
        return cls.objects.select_related().all()

    async def post_create(self) -> None:
        """
        Override this method to execute code after the object
        has been created
        """
        pass

    async def custom_actions(self, payload: dict[str, Any]):
        """
        Override this method to execute custom actions based on
        custom given fields. It could be useful for post create method.
        """
        pass

    @classmethod
    def get_reverse_relation_schema(
        cls, obj: type["ModelSerializer"], rel_type: type[REL_TYPES], field: str
    ):
        cls_f = []
        for rel_f in obj.ReadSerializer.fields:
            rel_f_obj = getattr(obj, rel_f)
            if (
                isinstance(
                    rel_f_obj.field,
                    (
                        models.ForeignKey,
                        models.OneToOneField,
                    ),
                )
                and rel_f_obj.field.related_model == cls
            ):
                cls_f.append(rel_f)
                obj.ReadSerializer.fields.remove(rel_f)
                continue
            if isinstance(rel_f_obj.field, models.ManyToManyField):
                cls_f.append(rel_f)
                obj.ReadSerializer.fields.remove(rel_f)

        rel_schema = obj.generate_read_s(depth=0)
        if rel_type == "many":
            rel_schema = list[rel_schema]
        rel_data = (
            field,
            rel_schema | None,
            None,
        )
        if len(cls_f) > 0:
            obj.ReadSerializer.fields.append(*cls_f)
        return rel_data

    @classmethod
    def get_schema_out_data(cls):
        fields = []
        reverse_rels = []
        for f in cls.ReadSerializer.fields:
            field_obj = getattr(cls, f)
            if isinstance(field_obj, ManyToManyDescriptor):
                rel_obj: ModelSerializer = field_obj.field.related_model
                if field_obj.reverse:
                    rel_obj: ModelSerializer = field_obj.field.model
                rel_data = cls.get_reverse_relation_schema(rel_obj, "many", f)
                reverse_rels.append(rel_data)
                continue
            if isinstance(field_obj, ReverseManyToOneDescriptor):
                rel_obj: ModelSerializer = field_obj.field.model
                rel_data = cls.get_reverse_relation_schema(rel_obj, "many", f)
                reverse_rels.append(rel_data)
                continue
            if isinstance(field_obj, ReverseOneToOneDescriptor):
                rel_obj: ModelSerializer = field_obj.related.related_model
                rel_data = cls.get_reverse_relation_schema(rel_obj, "one", f)
                reverse_rels.append(rel_data)
                continue
            fields.append(f)
        return fields, reverse_rels

    @classmethod
    def is_custom(cls, field: str):
        customs = cls.get_custom_fields("create") or []
        customs.extend(cls.get_custom_fields("update") or [])
        return any(field in custom_f for custom_f in customs)

    @classmethod
    async def parse_input_data(cls, request: HttpRequest, data: Schema):
        payload = data.model_dump()
        customs = {k: v for k, v in payload.items() if cls.is_custom(k)}
        for k, v in payload.items():
            if cls.is_custom(k):
                continue
            field_obj = getattr(cls, k).field
            if isinstance(field_obj, models.BinaryField):
                try:
                    payload |= {k: base64.b64decode(v)}
                except Exception as exc:
                    raise SerializeError({k: ". ".join(exc.args)}, 400)
            if isinstance(field_obj, models.ForeignKey):
                rel: ModelSerializer = await field_obj.related_model.get_object(
                    request, v
                )
                payload |= {k: rel}
        new_payload = {k: v for k, v in payload.items() if k not in customs}
        return new_payload, customs

    @classmethod
    async def parse_output_data(cls, request: HttpRequest, data: Schema):
        olds_k: list[dict] = []
        payload = data.model_dump()
        for k, v in payload.items():
            try:
                field_obj = getattr(cls, k).field
            except AttributeError:
                field_obj = getattr(cls, k).related
            if isinstance(v, dict) and (
                isinstance(field_obj, models.ForeignKey)
                or isinstance(field_obj, models.OneToOneField)
            ):
                rel: ModelSerializer = await field_obj.related_model.get_object(
                    request, list(v.values())[0]
                )
                if isinstance(field_obj, models.ForeignKey):
                    for rel_k, rel_v in v.items():
                        field_rel_obj = getattr(rel, rel_k)
                        if isinstance(field_rel_obj, models.ForeignKey):
                            olds_k.append({rel_k: rel_v})
                    for obj in olds_k:
                        for old_k, old_v in obj.items():
                            v.pop(old_k)
                            v |= {f"{old_k}_id": old_v}
                    olds_k = []
                payload |= {k: rel}
        return payload

    @classmethod
    def get_custom_fields(cls, s_type: type[S_TYPES]):
        try:
            match s_type:
                case "create":
                    customs = cls.CreateSerializer.customs
                case "update":
                    customs = cls.UpdateSerializer.customs
        except AttributeError:
            return None
        return customs

    @classmethod
    def generate_read_s(cls, depth: int = 1) -> Schema:
        fields, reverse_rels = cls.get_schema_out_data()
        customs = [custom for custom in reverse_rels]
        return create_schema(
            model=cls,
            name=f"{cls._meta.model_name}SchemaOut",
            depth=depth,
            fields=fields,
            custom_fields=customs,
        )

    @classmethod
    def generate_create_s(cls) -> Schema:
        return create_schema(
            model=cls,
            name=f"{cls._meta.model_name}SchemaIn",
            fields=cls.CreateSerializer.fields,
            custom_fields=cls.get_custom_fields("create"),
        )

    @classmethod
    def generate_update_s(cls) -> Schema:
        return create_schema(
            model=cls,
            name=f"{cls._meta.model_name}SchemaPatch",
            fields=cls.UpdateSerializer.fields,
            custom_fields=cls.get_custom_fields("update"),
        )

    @classmethod
    async def get_object(cls, request: HttpRequest, pk: int | str):
        q = {cls._meta.pk.attname: pk}
        try:
            obj = (
                await (await cls.queryset_request(request))
                .prefetch_related(*cls.get_reverse_relations())
                .aget(**q)
            )
        except ObjectDoesNotExist:
            raise SerializeError({cls._meta.model_name: "not found"}, 404)
        return obj

    @classmethod
    async def create_s(cls, request: HttpRequest, data: Schema):
        try:
            payload, customs = await cls.parse_input_data(request, data)
            pk = (await cls.objects.acreate(**payload)).pk
            obj = await cls.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error
        payload |= customs
        await obj.custom_actions(payload)
        await obj.post_create()
        return await cls.read_s(request, obj)

    @classmethod
    async def read_s(cls, request: HttpRequest, obj: type["ModelSerializer"]):
        schema = cls.generate_read_s().from_orm(obj)
        try:
            data = await cls.parse_output_data(request, schema)
        except SerializeError as e:
            return e.status_code, e.error
        return data

    @classmethod
    async def update_s(cls, request: HttpRequest, data: Schema, pk: int | str):
        try:
            obj = await cls.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error

        payload, customs = await cls.parse_input_data(request, data)
        for k, v in payload.items():
            if v is not None:
                setattr(obj, k, v)
        await obj.custom_actions(customs)
        await obj.asave()
        updated_object = await cls.get_object(request, pk)
        return await cls.read_s(request, updated_object)

    @classmethod
    async def delete_s(cls, request: HttpRequest, pk: int | str):
        try:
            obj = await cls.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error
        await obj.adelete()
        return HttpResponse(status=204)
