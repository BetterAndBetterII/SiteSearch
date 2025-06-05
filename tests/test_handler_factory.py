import sys, types
import importlib.util
from unittest.mock import MagicMock, patch
from pathlib import Path

# Stub handler modules to avoid heavy dependencies
for cls_name in ["crawler_handler", "cleaner_handler", "storage_handler", "indexer_handler"]:
    module_name = f"src.backend.sitesearch.handler.{cls_name}"
    mod = types.ModuleType(module_name)
    handler_cls = type(cls_name.title().replace('_', ''), (), {})
    setattr(mod, handler_cls.__name__, handler_cls)
    sys.modules[module_name] = mod

spec = importlib.util.spec_from_file_location(
    "src.backend.sitesearch.handler.handler_factory",
    Path(__file__).resolve().parents[1] / 'src/backend/sitesearch/handler/handler_factory.py'
)
handler_factory = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = handler_factory
spec.loader.exec_module(handler_factory)
HandlerFactory = handler_factory.HandlerFactory


def setup_function(func):
    HandlerFactory._handlers = {}


@patch('src.backend.sitesearch.handler.handler_factory.CrawlerHandler')
def test_create_crawler_singleton(mock_crawler):
    instance = MagicMock(name='crawler')
    mock_crawler.return_value = instance
    h1 = HandlerFactory.create_crawler_handler('redis://local', handler_id='c1')
    h2 = HandlerFactory.create_crawler_handler('redis://local', handler_id='c1')
    assert h1 is h2
    mock_crawler.assert_called_once()


@patch('src.backend.sitesearch.handler.handler_factory.IndexerHandler')
@patch('src.backend.sitesearch.handler.handler_factory.StorageHandler')
@patch('src.backend.sitesearch.handler.handler_factory.CleanerHandler')
@patch('src.backend.sitesearch.handler.handler_factory.CrawlerHandler')
def test_create_complete_pipeline(mock_crawler, mock_cleaner, mock_storage, mock_indexer):
    mock_crawler.return_value = MagicMock(name='crawler')
    mock_cleaner.return_value = MagicMock(name='cleaner')
    mock_storage.return_value = MagicMock(name='storage')
    mock_indexer.return_value = MagicMock(name='indexer')

    pipeline = HandlerFactory.create_complete_pipeline('redis://r', 'milvus://m', prefix='t', auto_start=False)

    assert set(pipeline.keys()) == {'crawler', 'cleaner', 'storage', 'indexer'}
    mock_crawler.assert_called_once()
    mock_cleaner.assert_called_once()
    mock_storage.assert_called_once()
    mock_indexer.assert_called_once()
