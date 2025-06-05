from unittest.mock import MagicMock, patch

from src.backend.sitesearch.pipeline_manager import MultiProcessSiteSearchManager


@patch('src.backend.sitesearch.pipeline_manager.redis.from_url')
def test_update_last_activity(mock_from_url):
    client = MagicMock(delete=lambda *a, **k: None)
    mock_from_url.return_value = client
    mgr = MultiProcessSiteSearchManager('redis://local')
    mgr.redis_client = MagicMock()  # avoid calls from setup_queues interfering
    mgr.update_last_activity('crawler')
    mgr.redis_client.set.assert_called_once()
    key, value = mgr.redis_client.set.call_args[0]
    assert key == 'sitesearch:last_activity:crawler'
    assert float(value) == float(value)  # value is timestamp string


@patch('src.backend.sitesearch.pipeline_manager.redis.from_url')
def test_record_processing_time(mock_from_url):
    client = MagicMock(delete=lambda *a, **k: None)
    mock_from_url.return_value = client
    mgr = MultiProcessSiteSearchManager('redis://local')
    mgr.redis_client = MagicMock()
    mgr.record_processing_time('cleaner', 1.5)
    mgr.redis_client.lpush.assert_called_once_with('sitesearch:processing_times:cleaner', '1.5')
    mgr.redis_client.ltrim.assert_called_once_with('sitesearch:processing_times:cleaner', 0, 99)
