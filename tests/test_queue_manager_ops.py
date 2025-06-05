from unittest.mock import MagicMock, patch
from tests.helpers import redis_stub  # noqa: F401
from src.backend.sitesearch.utils.queue_manager import QueueManager


@patch('src.backend.sitesearch.utils.queue_manager.redis.from_url')
def test_simple_operations(mock_from_url):
    client = MagicMock()
    client.llen.return_value = 5
    client.get.return_value = b'{"id": "t1"}'
    client.hgetall.return_value = {b'pending': b'2', b'processing': b'1', b'completed': b'3', b'failed': b'0', b'total_processing_time': b'6'}
    mock_from_url.return_value = client

    qm = QueueManager('redis://local')
    assert qm.get_queue_length('q') == 5
    assert qm.get_task_status('t1') == {"id": "t1"}
    metrics = qm.get_queue_metrics('q')
    assert metrics.pending_tasks == 2
    assert metrics.avg_processing_time == 2.0  # 6 / 3
