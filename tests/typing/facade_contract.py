from typing import Any
from typing_extensions import assert_type
from django.db import models
from ninja_aio import ModelSerializer, Serializer
from ninja_aio.types import BulkResult

class Book(ModelSerializer):
    pass

class PlainBook(models.Model):
    pass

class BookSerializer(Serializer[PlainBook]):
    class Meta:
        model = PlainBook

def sync_contract(book: Book, plain: PlainBook) -> None:
    assert_type(Book.create({}), Book)
    assert_type(Book.get(pk=1), Book)
    assert_type(Book.update(book, {}), Book)
    assert_type(Book.destroy(book), None)
    assert_type(Book.model_dump(book), dict[str, Any])
    assert_type(Book.model_dumps([book]), list[dict[str, Any]])
    assert_type(Book.bulk_create([{}]), BulkResult[Book])
    assert_type(BookSerializer.create({}), PlainBook)
    assert_type(BookSerializer.get(pk=1), PlainBook)
    assert_type(BookSerializer.update(plain, {}), PlainBook)
    assert_type(BookSerializer.destroy(plain), None)
    assert_type(BookSerializer.model_dump(plain), dict[str, Any])
    assert_type(BookSerializer.model_dumps([plain]), list[dict[str, Any]])
    assert_type(BookSerializer.bulk_create([{}]), BulkResult[PlainBook])

async def async_contract(book: Book, plain: PlainBook) -> None:
    assert_type(await Book.acreate({}), Book)
    assert_type(await Book.aget(pk=1), Book)
    assert_type(await Book.aupdate(book, {}), Book)
    assert_type(await Book.adestroy(book), None)
    assert_type(await Book.amodel_dump(book), dict[str, Any])
    assert_type(await Book.amodel_dumps([book]), list[dict[str, Any]])
    assert_type(await Book.abulk_create([{}]), BulkResult[Book])
    assert_type(await BookSerializer.acreate({}), PlainBook)
    assert_type(await BookSerializer.aget(pk=1), PlainBook)
    assert_type(await BookSerializer.aupdate(plain, {}), PlainBook)
    assert_type(await BookSerializer.adestroy(plain), None)
    assert_type(await BookSerializer.amodel_dump(plain), dict[str, Any])
    assert_type(await BookSerializer.amodel_dumps([plain]), list[dict[str, Any]])
    assert_type(await BookSerializer.abulk_create([{}]), BulkResult[PlainBook])
