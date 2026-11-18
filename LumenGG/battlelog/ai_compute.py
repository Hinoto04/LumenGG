"""Choose AI moves in worker processes, away from the websocket server.

Choosing a Ready card with engine evaluation runs dozens of battle
simulations. Doing that inside the Daphne process would hold Python's GIL
and slow every other connection, so ``choose_ai_decision`` sends the pure
computation to a process pool. The caller (``automatic_services``) still
writes the command and broadcasts it, so the channel layer and database
stay in the server process.

Settings
- ``LUMEN_AI_PROCESS_POOL`` (default ``True``): use worker processes.
  Tests set it to ``False`` and compute in-process.
- ``LUMEN_AI_WORKERS`` (default: half the CPUs, at least 1): pool size; at
  most this many AI decisions are computed at once, the rest wait in line.
- ``LUMEN_AI_ENGINE_READY_EVAL`` (default ``True``): engine-simulated Ready
  cells. Under load (more queued decisions than ``LUMEN_AI_SHED_QUEUE``
  times the pool size) a decision falls back to base-stat cells.
"""

import os
import threading
from concurrent.futures import ProcessPoolExecutor

from django.conf import settings

SHED_QUEUE_FACTOR = 2
_pool = None
_pool_guard = threading.Lock()
_pending = 0


def worker_count():
    configured = getattr(settings, 'LUMEN_AI_WORKERS', None)
    if configured:
        return max(1, int(configured))
    return max(1, (os.cpu_count() or 2) // 2)


def _init_worker(settings_module):
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    import django

    django.setup()


def _get_pool():
    global _pool
    with _pool_guard:
        if _pool is None:
            _pool = ProcessPoolExecutor(
                max_workers=worker_count(),
                initializer=_init_worker,
                initargs=(os.environ.get('DJANGO_SETTINGS_MODULE', 'LumenGG.settings'),),
            )
        return _pool


def pending_decisions():
    return _pending


def _engine_eval_allowed():
    if not getattr(settings, 'LUMEN_AI_ENGINE_READY_EVAL', True):
        return False
    factor = getattr(settings, 'LUMEN_AI_SHED_QUEUE', SHED_QUEUE_FACTOR)
    return _pending < worker_count() * factor


def compute_decision(job):
    """Pure computation: build the engine from ``job`` and choose a move."""
    from django.utils.dateparse import parse_datetime

    from .automatic_services import _cached_ruleset
    from .game.ai import choose_action
    from .game.ai_outcomes import build_ready_evaluator
    from .game.engine import AutomaticGameEngine

    engine = AutomaticGameEngine(
        job['state'], _cached_ruleset(job['release_id']), version=job['version'],
        now=parse_datetime(job['now']), events=[], seed=job['engine_seed'],
    )
    role = job['role']
    observation = engine.observe(role, include_memory=True)
    # 레디 결과표: 기본은 카드별 수치표(table). 판정을 바꾸는 카드의 칸을 엔진으로 다시 볼지는
    # LUMEN_AI_TABLE_ENGINE_CELLS(기본 끔: 대전 측정에서 승률 차이가 없고 레디당 1초가 더 듦).
    # 부하가 높으면(engine_eval=False) 엔진 칸은 늘 생략한다.
    mode = job.get('ready_eval') or 'table'
    engine_cells = job['engine_eval'] and (mode != 'table' or job.get('table_engine_cells', False))
    evaluator = build_ready_evaluator(
        engine, observation, role, mode=mode,
        weights=job['weights'], profile=job['profile'], engine_cells=engine_cells,
    )
    return choose_action(
        observation, role, weights=job['weights'], seed=job['seed'],
        profile=job['profile'], ready_evaluator=evaluator,
    )


def choose_ai_decision(job):
    """Decision for one AI seat; ``job`` holds only plain data.

    Uses the process pool unless ``LUMEN_AI_PROCESS_POOL`` is off.
    """
    global _pending
    job = {
        **job,
        'engine_eval': bool(job.get('engine_eval', True)) and _engine_eval_allowed(),
        'ready_eval': job.get('ready_eval') or getattr(settings, 'LUMEN_AI_READY_EVAL', 'table'),
        'table_engine_cells': getattr(settings, 'LUMEN_AI_TABLE_ENGINE_CELLS', False),
    }
    if not getattr(settings, 'LUMEN_AI_PROCESS_POOL', True):
        return compute_decision(job)
    with _pool_guard:
        _pending += 1
    try:
        return _get_pool().submit(compute_decision, job).result()
    finally:
        with _pool_guard:
            _pending -= 1
