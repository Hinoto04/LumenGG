"""AI 결정 계산을 작업 프로세스로 보내는 경로(ai_compute)와 부하 시 엔진 평가 생략."""

from concurrent.futures import Future
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from . import ai_compute


class ImmediatePool:
    """submit 즉시 실행해 Future를 돌려주는 테스트용 풀."""

    def __init__(self):
        self.pending_seen = []

    def submit(self, fn, job):
        self.pending_seen.append(ai_compute.pending_decisions())
        future = Future()
        future.set_result(fn(job))
        return future


class AIComputeTests(SimpleTestCase):
    def test_in_process_when_the_pool_is_off(self):
        with patch.object(ai_compute, 'compute_decision', return_value='decided') as compute:
            self.assertEqual(ai_compute.choose_ai_decision({'role': 'p2'}), 'decided')

        self.assertTrue(compute.call_args.args[0]['engine_eval'])

    @override_settings(LUMEN_AI_PROCESS_POOL=True, LUMEN_AI_WORKERS=2)
    def test_pool_path_counts_pending_decisions(self):
        pool = ImmediatePool()
        with patch.object(ai_compute, '_get_pool', return_value=pool), \
                patch.object(ai_compute, 'compute_decision', side_effect=lambda job: job['role']):
            self.assertEqual(ai_compute.choose_ai_decision({'role': 'p2'}), 'p2')

        self.assertEqual(pool.pending_seen, [1])
        self.assertEqual(ai_compute.pending_decisions(), 0)

    @override_settings(LUMEN_AI_WORKERS=2, LUMEN_AI_SHED_QUEUE=2)
    def test_engine_evaluation_is_shed_under_load(self):
        with patch.object(ai_compute, '_pending', 4), \
                patch.object(ai_compute, 'compute_decision', side_effect=lambda job: job['engine_eval']):
            self.assertFalse(ai_compute.choose_ai_decision({'role': 'p2'}))
        with patch.object(ai_compute, '_pending', 3), \
                patch.object(ai_compute, 'compute_decision', side_effect=lambda job: job['engine_eval']):
            self.assertTrue(ai_compute.choose_ai_decision({'role': 'p2'}))

    @override_settings(LUMEN_AI_ENGINE_READY_EVAL=False)
    def test_engine_evaluation_can_be_turned_off(self):
        with patch.object(ai_compute, 'compute_decision', side_effect=lambda job: job['engine_eval']):
            self.assertFalse(ai_compute.choose_ai_decision({'role': 'p2'}))

    @override_settings(LUMEN_AI_WORKERS=None)
    def test_default_worker_count_is_half_the_cpus(self):
        with patch('os.cpu_count', return_value=8):
            self.assertEqual(ai_compute.worker_count(), 4)
        with patch('os.cpu_count', return_value=1):
            self.assertEqual(ai_compute.worker_count(), 1)

    def test_table_evaluation_is_the_default_without_engine_cells(self):
        with patch.object(ai_compute, 'compute_decision', side_effect=lambda job: job):
            job = ai_compute.choose_ai_decision({'role': 'p2'})

        self.assertEqual(job['ready_eval'], 'table')
        self.assertFalse(job['table_engine_cells'])

    @override_settings(LUMEN_AI_READY_EVAL='engine', LUMEN_AI_TABLE_ENGINE_CELLS=True)
    def test_ready_evaluation_follows_settings(self):
        with patch.object(ai_compute, 'compute_decision', side_effect=lambda job: job):
            job = ai_compute.choose_ai_decision({'role': 'p2'})

        self.assertEqual(job['ready_eval'], 'engine')
        self.assertTrue(job['table_engine_cells'])
