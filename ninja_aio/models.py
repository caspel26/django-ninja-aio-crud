import base64
from typing import Literal

from ninja.schema import Schema
from ninja.orm import create_schema

from django.db import models
from django.http import HttpResponse, HttpRequest
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.fields.related import OneToOneRel
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
)

from .exceptions import SerializeError

S_TYPES = Literal["read", "create", "update"]


class ModelSerializer(models.Model):
    class Meta:
        abstract = True

    class CreateSerializer:
        fields: list[str] = []
        optionals: list[str] = []
        customs: list[str] = []

    class ReadSerializer:
        fields: list[str] = []
        customs: list[str] = []

    class UpdateSerializer:
        fields: list[str] = []
        customs: list[str] = []

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

    @classmethod
    def get_reverse_relations(cls):
        reverse_rels = []
        for f in cls.ReadSerializer.fields:
            field_obj = getattr(cls, f)
            if isinstance(field_obj, ReverseManyToOneDescriptor):
                reverse_rels.append(field_obj.field.__dict__.get("_related_name"))
            if isinstance(field_obj, ReverseOneToOneDescriptor):
                reverse_rels.append(
                    list(field_obj.__dict__.values())[0].__dict__.get("related_name")
                )
        return reverse_rels

    @classmethod
    def get_reverse_relation_schema(
        cls, obj: "ModelSerializer", s_type: str, field: str
    ):
        for index, rel_f in enumerate(obj.ReadSerializer.fields):
            if rel_f == cls._meta.model_name:
                obj.ReadSerializer.fields.pop(index)
                break
        rel_schema = obj.generate_read_s(depth=0)
        if s_type == "many":
            rel_schema = list[rel_schema]
        rel_data = (
            field,
            rel_schema | None,
            None,
        )
        obj.ReadSerializer.fields.append(cls._meta.model_name)
        return rel_data

    @classmethod
    def get_schema_out_data(cls):
        fields = []
        reverse_rels = []
        s_type = ""
        for f in cls.ReadSerializer.fields:
            field_obj = getattr(cls, f)
            if isinstance(field_obj, ReverseManyToOneDescriptor):
                rel_obj: ModelSerializer = field_obj.field.__dict__.get("model")
                s_type = "many"
                rel_data = cls.get_reverse_relation_schema(rel_obj, s_type, f)
                reverse_rels.append(rel_data)
                continue
            if isinstance(field_obj, ReverseOneToOneDescriptor):
                rel_obj: ModelSerializer = list(field_obj.__dict__.values())[
                    0
                ].__dict__.get("related_model")
                s_type = "one"
                rel_data = cls.get_reverse_relation_schema(rel_obj, s_type, f)
                reverse_rels.append(rel_data)
                continue
            fields.append(f)
        return fields, reverse_rels

    @classmethod
    async def parse_input_data(cls, request: HttpRequest, data: Schema):
        payload = data.model_dump()
        for k, v in payload.items():
            field_obj = getattr(cls, k).field
            if isinstance(field_obj, models.BinaryField):
                if not v.endswith(b"=="):
                    v = v + b"=="
                payload |= {k: base64.b64decode(v)}
            if isinstance(field_obj, models.ForeignKey):
                try:
                    rel: ModelSerializer = await field_obj.related_model.get_object(
                        request, v
                    )
                except ObjectDoesNotExist:
                    raise SerializeError({k: "not found"}, 404)
                payload |= {k: rel}
        return payload

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
                or isinstance(field_obj, OneToOneRel)
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
                case "read":
                    customs = cls.ReadSerializer.customs
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
        customs = [custom for custom in reverse_rels + cls.get_custom_fields("read")]
        return create_schema(
            model=cls,
            name=f"{cls._meta.model_name}SchemaOut",
            depth=depth,
            fields=fields,
            custom_fields=customs,
        )

    @classmethod
    def generate_create_s(cls) -> Schema:
        try:
            optional_fields = cls.CreateSerializer.optionals
        except AttributeError:
            optional_fields = None
        return create_schema(
            model=cls,
            name=f"{cls._meta.model_name}SchemaIn",
            fields=cls.CreateSerializer.fields,
            optional_fields=optional_fields,
            custom_fields=cls.get_custom_fields("create"),
        )

    @classmethod
    def generate_update_s(cls) -> Schema:
        return create_schema(
            model=cls,
            name=f"{cls._meta.model_name}SchemaPatch",
            fields=cls.UpdateSerializer.fields,
            optional_fields=cls.UpdateSerializer.fields,
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
            pk = (
                await cls.objects.acreate(**await cls.parse_input_data(request, data))
            ).pk
            obj = await cls.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error
        await obj.post_create()
        return await cls.read_s(request, obj)

    @classmethod
    async def read_s(cls, request: HttpRequest, obj: "ModelSerializer"):
        schema = cls.generate_read_s().from_orm(obj)
        return await cls.parse_output_data(request, schema)

    @classmethod
    async def update_s(cls, request: HttpRequest, data: Schema, pk: int | str):
        try:
            obj = await cls.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error

        payload = await cls.parse_input_data(request, data)
        for k, v in payload.items():
            if v is not None:
                setattr(obj, k, v)
        await obj.asave()
        return await cls.read_s(request, obj)

    @classmethod
    async def delete_s(cls, request: HttpRequest, pk: int | str):
        try:
            obj = await cls.get_object(request, pk)
        except SerializeError as e:
            return e.status_code, e.error
        await obj.adelete()
        return HttpResponse(status=204)
