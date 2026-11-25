from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.test import TestCase, override_settings

from apps.core.db_storage import DatabaseStorage
from apps.core.models import StoredFile

DB_STORAGES = {
    "default": {"BACKEND": "apps.core.db_storage.DatabaseStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class DatabaseStorageTests(TestCase):
    def setUp(self):
        self.storage = DatabaseStorage()

    def test_save_open_exists_size_delete(self):
        name = self.storage.save("catalog/products/a.png", ContentFile(b"\x89PNG-bytes"))
        self.assertEqual(name, "catalog/products/a.png")
        self.assertTrue(self.storage.exists(name))
        self.assertEqual(self.storage.size(name), len(b"\x89PNG-bytes"))
        with self.storage.open(name) as handle:
            self.assertEqual(handle.read(), b"\x89PNG-bytes")
        self.assertEqual(StoredFile.objects.get(name=name).content_type, "image/png")
        self.storage.delete(name)
        self.assertFalse(self.storage.exists(name))

    def test_duplicate_name_gets_unique_name(self):
        first = self.storage.save("catalog/products/a.png", ContentFile(b"one"))
        second = self.storage.save("catalog/products/a.png", ContentFile(b"two"))
        self.assertNotEqual(first, second)
        with self.storage.open(first) as handle:
            self.assertEqual(handle.read(), b"one")

    def test_url_uses_media_url(self):
        self.assertEqual(self.storage.url("catalog/products/a b.png"), "/media/catalog/products/a%20b.png")


@override_settings(STORAGES=DB_STORAGES)
class ServeMediaTests(TestCase):
    def test_serves_file_from_database(self):
        DatabaseStorage().save("catalog/products/x.png", ContentFile(b"IMG"))
        response = self.client.get("/media/catalog/products/x.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, b"IMG")
        self.assertIn("sandbox", response["Content-Security-Policy"])

    def test_missing_file_is_404(self):
        self.assertEqual(self.client.get("/media/catalog/products/none.png").status_code, 404)

    def test_default_storage_is_database_storage(self):
        self.assertIsInstance(storages["default"], DatabaseStorage)
