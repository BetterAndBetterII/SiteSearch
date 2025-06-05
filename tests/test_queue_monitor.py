from unittest.mock import MagicMock
import importlib
from src.backend.sitesearch.utils.queue_manager import QueueMetrics

import src.backend.sitesearch.utils.queue_monitor as qm


def setup_function(func):
    qm._queue_monitor_instance = None


def teardown_function(func):
    qm._queue_monitor_instance = None


def test_get_queue_monitor_singleton(monkeypatch):
    dummy_qm = MagicMock()
    monkeypatch.setattr(qm, 'get_queue_manager', lambda: dummy_qm)
    monitor1 = qm.get_queue_monitor(queue_names=['q1'])
    monitor2 = qm.get_queue_monitor(queue_names=['q2'])
    assert monitor1 is monitor2
    assert monitor1.queue_names == ['q1']


def test_summary_report(monkeypatch):
    metrics = {
        'q1': QueueMetrics(queue_name='q1', pending_tasks=1, completed_tasks=1),
        'q2': QueueMetrics(queue_name='q2', pending_tasks=2001, completed_tasks=1, failed_tasks=2),
    }
    dummy = MagicMock()
    dummy.get_queue_metrics.side_effect = lambda name: metrics[name]
    monkeypatch.setattr(qm, 'get_queue_manager', lambda: dummy)
    monitor = qm.get_queue_monitor(queue_names=['q1', 'q2'], max_pending_threshold=1000, max_error_rate=0.1)
    monitor._check_queue_health('q1')
    monitor._check_queue_health('q2')
    report = monitor.get_summary_report()
    assert report['total_queues'] == 2
    assert report['unhealthy_queues'] == 1
    assert report['total_pending_tasks'] == 2002
    assert any(d['name'] == 'q2' for d in report['unhealthy_details'])
