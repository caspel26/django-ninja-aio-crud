import asyncio
from typing import Coroutine

from django.http import HttpRequest
from ninja import Path, Query
from ninja.pagination import paginate
from ninja_aio.decorators import unique_view
from ninja_aio.models import ModelSerializer, ModelUtil
from ninja_aio.schemas import (
    GenericMessageSchema,
    M2MRelationSchema,
    M2MSchemaIn,
    M2MSchemaOut,
    M2MAddSchemaIn,
    M2MRemoveSchemaIn,
)
from django.db.models import QuerySet, Model


class ManyToManyAPI:
    def __init__(
        self,
        relations: list[M2MRelationSchema],
        view_set,
    ):
        from ninja_aio.views import APIViewSet
        self.relations = relations
        self.view_set: APIViewSet = view_set
        self.router = view_set.router
        self.pagination_class = view_set.pagination_class
        self.path_schema = view_set.path_schema
        self.related_model_util = ModelUtil(view_set.model_util)
        self.relations_filters_schemas = self._generate_m2m_filters_schemas()

    def _generate_m2m_filters_schemas(self):
        """
        Build per-relation filters schemas for M2M endpoints.
        """
        return {
            data.related_name: self.view_set._generate_schema(
                {} if not data.filters else data.filters,
                f"{self.related_model_util.model_name}{data.related_name.capitalize()}FiltersSchema",
            )
            for data in self.relations
        }

    def _get_query_handler(self, related_name: str) -> Coroutine | None:
        return getattr(self.view_set, f"{related_name}_query_params_handler", None)

    async def _check_m2m_objs(
        self,
        request: HttpRequest,
        objs_pks: list,
        model: ModelSerializer | Model,
        related_manager: QuerySet,
        remove: bool = False,
    ):
        """
        Validate requested add/remove pk list for M2M operations.
        Returns (errors, details, objects_to_process).
        """
        errors, objs_detail, objs = [], [], []
        rel_objs = [rel_obj async for rel_obj in related_manager.select_related().all()]
        rel_model_name = model._meta.verbose_name.capitalize()
        for obj_pk in objs_pks:
            rel_obj = await (
                await ModelUtil(model).get_object(request, filters={"pk": obj_pk})
            ).afirst()
            if rel_obj is None:
                errors.append(f"{rel_model_name} with pk {obj_pk} not found.")
                continue
            if remove ^ (rel_obj in rel_objs):
                errors.append(
                    f"{rel_model_name} with id {obj_pk} is {'not ' if remove else ''}in {self.model_util.model_name}"
                )
                continue
            objs.append(rel_obj)
            objs_detail.append(
                f"{rel_model_name} with id {obj_pk} successfully {'removed' if remove else 'added'}"
            )
        return errors, objs_detail, objs

    async def _collect_m2m(
        self,
        request: HttpRequest,
        pks: list,
        model: ModelSerializer | Model,
        related_manager: QuerySet,
        remove=False,
    ):
        if not pks:
            return ([], [], [])
        return await self._check_m2m_objs(
            request, pks, model, related_manager, remove=remove
        )

    def _build_views(self, relation: M2MRelationSchema):
        model = relation.model
        related_name = relation.related_name
        m2m_auth = relation.auth or self.m2m_auth
        rel_util = ModelUtil(model)
        rel_path = relation.path or rel_util.verbose_name_path_resolver()
        related_schema = model.generate_related_s()

        m2m_add = relation.add
        m2m_remove = relation.remove
        m2m_get = relation.get
        filters_schema = self.m2m_filters_schemas.get(related_name)

        # GET related
        if m2m_get:

            @self.router.get(
                f"{self.path_retrieve}{rel_path}",
                response={
                    200: list[related_schema],
                    self.error_codes: GenericMessageSchema,
                },
                auth=m2m_auth,
                summary=f"Get {rel_util.model._meta.verbose_name_plural.capitalize()}",
                description=f"Get all related {rel_util.model._meta.verbose_name_plural.capitalize()}",
            )
            @unique_view(f"get_{self.related_model_util.model_name}_{rel_path}")
            @paginate(self.pagination_class)
            async def get_related(
                request: HttpRequest,
                pk: Path[self.path_schema],  # type: ignore
                filters: Query[filters_schema] = None,  # type: ignore
            ):
                obj = await self.related_model_util.get_object(
                    request, self.view_set._get_pk(pk)
                )
                related_manager = getattr(obj, related_name)
                related_qs = related_manager.all()

                query_handler = self._get_query_handler(related_name)
                if filters is not None and query_handler:
                    related_qs = await query_handler(related_qs, filters.model_dump())

                return [
                    await rel_util.read_s(request, rel_obj, related_schema)
                    async for rel_obj in related_qs
                ]

        # ADD / REMOVE related
        if m2m_add or m2m_remove:
            plural = rel_util.model._meta.verbose_name_plural.capitalize()
            action_map = {
                (True, True): ("Add or Remove", M2MSchemaIn),
                (True, False): ("Add", M2MAddSchemaIn),
                (False, True): ("Remove", M2MRemoveSchemaIn),
            }
            action, schema_in = action_map[(m2m_add, m2m_remove)]
            summary = f"{action} {plural}"
            description = summary

            @self.router.post(
                f"{self.path_retrieve}{rel_path}/",
                response={200: M2MSchemaOut, self.error_codes: GenericMessageSchema},
                auth=m2m_auth,
                summary=summary,
                description=description,
            )
            @unique_view(f"manage_{self.related_model_util.model_name}_{rel_path}")
            async def manage_related(
                request: HttpRequest,
                pk: Path[self.path_schema],  # type: ignore
                data: schema_in,  # type: ignore
            ):
                obj = await self.related_model_util.get_object(
                    request, self.view_set._get_pk(pk)
                )
                related_manager: QuerySet = getattr(obj, related_name)

                add_pks = getattr(data, "add", []) if m2m_add else []
                remove_pks = getattr(data, "remove", []) if m2m_remove else []

                add_errors, add_details, add_objs = await self._collect_m2m(
                    request, add_pks, model, related_manager
                )
                remove_errors, remove_details, remove_objs = await self._collect_m2m(
                    request, remove_pks, model, related_manager, remove=True
                )

                tasks = []
                if add_objs:
                    tasks.append(related_manager.aadd(*add_objs))
                if remove_objs:
                    tasks.append(related_manager.aremove(*remove_objs))
                if tasks:
                    await asyncio.gather(*tasks)

                results = add_details + remove_details
                errors = add_errors + remove_errors

                return {
                    "results": {"count": len(results), "details": results},
                    "errors": {"count": len(errors), "details": errors},
                }

    def _add_views(self):
        for relation in self.relations:
            self._build_views(relation)
