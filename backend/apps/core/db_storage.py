import mimetypes
from urllib.parse import quote, urljoin

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


def _clean(name: str) -> str:
    return str(name).replace("\\", "/").lstrip("/")


@deconstructible
class DatabaseStorage(Storage):
    """Fayllarni Postgres jadvalida (StoredFile) saqlaydigan Django storage."""

    @staticmethod
    def _model():
        from apps.core.models import StoredFile

        return StoredFile

    def _open(self, name, mode="rb"):
        try:
            obj = self._model().objects.only("content").get(name=_clean(name))
        except self._model().DoesNotExist as exc:
            raise FileNotFoundError(name) from exc
        return ContentFile(bytes(obj.content), name=_clean(name))

    def _save(self, name, content):
        name = _clean(name)
        content.seek(0)
        data = content.read()
        if isinstance(data, str):
            data = data.encode()
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        self._model().objects.update_or_create(
            name=name,
            defaults={"content": data, "content_type": content_type, "size": len(data)},
        )
        return name

    def exists(self, name):
        return self._model().objects.filter(name=_clean(name)).exists()

    def delete(self, name):
        self._model().objects.filter(name=_clean(name)).delete()

    def size(self, name):
        try:
            return self._model().objects.values_list("size", flat=True).get(name=_clean(name))
        except self._model().DoesNotExist as exc:
            raise FileNotFoundError(name) from exc

    def url(self, name):
        return urljoin(settings.MEDIA_URL, quote(_clean(name)))
