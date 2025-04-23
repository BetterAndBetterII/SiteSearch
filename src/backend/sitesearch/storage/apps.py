from django.apps import AppConfig

class StorageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'src.backend.sitesearch.storage'
    label = 'sitesearch_storage' 