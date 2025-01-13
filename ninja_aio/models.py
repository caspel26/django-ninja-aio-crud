import base64
from typing import Any

from ninja import Schema
from ninja.orm import create_schema

from django.db import models
from django.http import HttpRequest
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.fields.related_descriptors import (
    ReverseManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    ManyToManyDescriptor,
)

from .exceptions import SerializeError
from .types import S_TYPES, REL_TYPES, F_TYPES, SCHEMA_TYPES, ModelSerializerMeta


class ModelUtil:
    def __init__(self, model: type["ModelSerializer"] | models.Model):
        self.model = model

    @property
    def serializable_fields(self):
        if isinstance(self.model, ModelSerializerMeta):
            return self.model.get_fields("read")
        return [field.name for field in self.model._meta.get_fields()]

    @property
    def model_name(self) -> str:
        return self.model._meta.model_name

    @property
    def model_pk_name(self) -> str:
        return self.model._meta.pk.attname

    @property
    def model_verbose_name_plural(self) -> str:
        return self.model._meta.verbose_name_plural

    def verbose_name_path_resolver(self) -> str:
        return "-".join(self.model_verbose_name_plural.split(" "))

    def verbose_name_view_resolver(self) -> str:
        return self.model_verbose_name_plural.replace(" ", "")

    async def get_object(
        self,
        request: HttpRequest,
        pk: int | str = None,
        filters: dict = None,
        getters: dict = None,
    ):
        get_q = {self.model_pk_name: pk} if pk is not None else {}
        if getters:
            get_q |= getters

        obj_qs = self.model.objects.select_related()
        if isinstance(self.model, ModelSerializerMeta):
            obj_qs = await self.model.queryset_request(request)

        obj_qs = obj_qs.prefetch_related(*self.get_reverse_relations())
        if filters:
            obj_qs = obj_qs.filter(**filters)

        try:
            obj = await obj_qs.aget(**get_q)
        except ObjectDoesNotExist:
            raise SerializeError({self.model_name: "not found"}, 404)

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
        optionals = []
        if isinstance(self.model, ModelSerializerMeta):
            customs = {k: v for k, v in payload.items() if self.model.is_custom(k)}
            optionals = [
                k for k, v in payload.items() if self.model.is_optional(k) and v is None
            ]
        for k, v in payload.items():
            if isinstance(self.model, ModelSerializerMeta):
                if self.model.is_custom(k):
                    continue
                if self.model.is_optional(k) and k is None:
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
        new_payload = {
            k: v for k, v in payload.items() if k not in (customs.keys() or optionals)
        }
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
        payload, customs = await self.parse_input_data(request, data)
        pk = (await self.model.objects.acreate(**payload)).pk
        obj = await self.get_object(request, pk)
        if isinstance(self.model, ModelSerializerMeta):
            await obj.custom_actions(customs)
            await obj.post_create()
        return await self.read_s(request, obj, obj_schema)

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
        obj = await self.get_object(request, pk)
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
        obj = await self.get_object(request, pk)
        await obj.adelete()
        return None


class ModelSerializer(models.Model, metaclass=ModelSerializerMeta):
    class Meta:
        abstract = True

    class CreateSerializer:
        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    class ReadSerializer:
        fields: list[str] = []
        excludes: list[str] = []

    class UpdateSerializer:
        fields: list[str] = []
        customs: list[tuple[str, type, Any]] = []
        optionals: list[tuple[str, type]] = []
        excludes: list[str] = []

    @property
    def has_custom_fields_create(self):
        return hasattr(self.CreateSerializer, "customs")

    @property
    def has_custom_fields_update(self):
        return hasattr(self.UpdateSerializer, "customs")

    @property
    def has_custom_fields(self):
        return self.has_custom_fields_create or self.has_custom_fields_update

    @property
    def has_optional_fields_create(self):
        return hasattr(self.CreateSerializer, "optionals")

    @property
    def has_optional_fields_update(self):
        return hasattr(self.UpdateSerializer, "optionals")

    @property
    def has_optional_fields(self):
        return self.has_optional_fields_create or self.has_optional_fields_update

    @classmethod
    def _get_fields(cls, s_type: type[S_TYPES], f_type: type[F_TYPES]):
        match s_type:
            case "create":
                fields = getattr(cls.CreateSerializer, f_type, [])
            case "update":
                fields = getattr(cls.UpdateSerializer, f_type, [])
            case "read":
                fields = getattr(cls.ReadSerializer, f_type, [])
        return fields

    @classmethod
    def _is_special_field(
        cls, s_type: type[S_TYPES], field: str, f_type: type[F_TYPES]
    ):
        special_fields = cls._get_fields(s_type, f_type)
        return any(field in special_f for special_f in special_fields)

    @classmethod
    def _generate_model_schema(
        cls,
        schema_type: type[SCHEMA_TYPES],
        depth: int = None,
    ) -> Schema:
        match schema_type:
            case "In":
                s_type = "create"
            case "Patch":
                s_type = "update"
            case "Out":
                fields, reverse_rels, excludes = cls.get_schema_out_data()
                if not fields and not reverse_rels and not excludes:
                    return None
                return create_schema(
                    model=cls,
                    name=f"{cls._meta.model_name}SchemaOut",
                    depth=depth,
                    fields=fields,
                    custom_fields=reverse_rels,
                    exclude=excludes,
                )
        fields = cls.get_fields(s_type)
        optionals = cls.get_optional_fields(s_type)
        customs = cls.get_custom_fields(s_type) + optionals
        excludes = cls.get_excluded_fields(s_type)
        if not fields and not excludes:
            fields = [f[0] for f in optionals]
        return (
            create_schema(
                model=cls,
                name=f"{cls._meta.model_name}Schema{schema_type}",
                fields=fields,
                custom_fields=customs,
                exclude=excludes,
            )
            if fields or customs or excludes
            else None
        )

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
        for f in cls.get_fields("read"):
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
        return fields, reverse_rels, cls.get_excluded_fields("read")

    @classmethod
    def is_custom(cls, field: str):
        return cls._is_special_field(
            "create", field, "customs"
        ) or cls._is_special_field("update", field, "customs")

    @classmethod
    def is_optional(cls, field: str):
        return cls._is_special_field(
            "create", field, "optionals"
        ) or cls._is_special_field("update", field, "optionals")

    @classmethod
    def get_custom_fields(cls, s_type: type[S_TYPES]):
        return cls._get_fields(s_type, "customs")

    @classmethod
    def get_optional_fields(cls, s_type: type[S_TYPES]):
        return [
            (field, field_type, None)
            for field, field_type in cls._get_fields(s_type, "optionals")
        ]

    @classmethod
    def get_excluded_fields(cls, s_type: type[S_TYPES]):
        return cls._get_fields(s_type, "excludes")

    @classmethod
    def get_fields(cls, s_type: type[S_TYPES]):
        return cls._get_fields(s_type, "fields")

    @classmethod
    def generate_read_s(cls, depth: int = 1) -> Schema:
        return cls._generate_model_schema("Out", depth)

    @classmethod
    def generate_create_s(cls) -> Schema:
        return cls._generate_model_schema("In")

    @classmethod
    def generate_update_s(cls) -> Schema:
        return cls._generate_model_schema("Patch")
