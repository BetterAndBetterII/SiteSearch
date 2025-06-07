from unittest.mock import MagicMock, patch

from tests.helpers import redis_stub  # noqa: F401
from src.backend.sitesearch.utils.queue_manager import QueueManager


@patch('src.backend.sitesearch.utils.queue_manager.redis.from_url')
def test_key_generation(mock_from_url):
    mock_from_url.return_value = MagicMock()
    manager = QueueManager('redis://localhost:6379')
    assert manager._get_queue_key('q') == 'sitesearch:queue:q'
    assert manager._get_processing_key('q') == 'sitesearch:processing:q'
    assert manager._get_completed_key('q') == 'sitesearch:completed:q'
    assert manager._get_failed_key('q') == 'sitesearch:failed:q'
    assert manager._get_task_meta_key('t') == 'sitesearch:task:meta:t'
    assert manager._get_stats_key('q') == 'sitesearch:stats:q'

@patch('src.backend.sitesearch.utils.queue_manager.redis.from_url')
def test_get_queue_manager_singleton(mock_from_url):
    mock_from_url.return_value = MagicMock(llen=lambda k: 0, hgetall=lambda k: {})
    import src.backend.sitesearch.utils.queue_manager as qm
    qm._queue_manager_instance = None
    first = qm.get_queue_manager('redis://1')
    second = qm.get_queue_manager('redis://2')
    assert first is second
