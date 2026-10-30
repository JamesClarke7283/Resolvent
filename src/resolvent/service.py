"""Disposable workers ensure timeouts stop computation, not just waiting."""

import asyncio
import multiprocessing as mp
import os
import sys
import threading

from pydantic import ValidationError

from resolvent.models import MathError, MathRequest, MathResult


def _worker(connection, payload, timeout):
    try:
        if sys.platform == "linux":
            import resource

            # A runaway symbolic calculation cannot consume an unbounded CPU or
            # address space. The wall-clock timeout is enforced by the parent.
            resource.setrlimit(resource.RLIMIT_CPU, (int(timeout) + 1, int(timeout) + 2))
            limit = 2 * 1024**3
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
        from resolvent.engine import compute

        result = compute(payload)
        connection.send({"ok": True, "result": result.model_dump()})
    except MathError as exc:
        connection.send({"ok": False, "message": str(exc), "code": exc.code})
    except (Exception, MemoryError) as exc:
        connection.send(
            {"ok": False, "message": f"Calculation failed: {str(exc)[:300]}", "code": "calculation_error"}
        )
    finally:
        connection.close()


class MathService:
    def __init__(self, timeout: float = 15, concurrency: int = 2):
        self.timeout = timeout
        self._slots = threading.BoundedSemaphore(concurrency)

    def calculate(self, request: MathRequest | dict) -> MathResult:
        try:
            request = request if isinstance(request, MathRequest) else MathRequest.model_validate(request)
        except ValidationError as exc:
            raise MathError(str(exc), "invalid_request") from exc
        if not self._slots.acquire(blocking=False):
            raise MathError("The engine is busy. Try again after the current calculation finishes.", "busy")
        context = mp.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        process = context.Process(
            target=_worker, args=(send, request.model_dump(), self.timeout), daemon=True
        )
        try:
            # Limit BLAS threads in child workers. Avoid huge virtual-memory arenas
            # and excessive CPU use on machines with many cores.
            os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
            os.environ.setdefault("OMP_NUM_THREADS", "1")
            process.start()
            send.close()
            if not receive.poll(self.timeout):
                raise MathError(f"Calculation exceeded the {self.timeout:g}-second time limit.", "timeout")
            try:
                message = receive.recv()
            except EOFError as exc:
                raise MathError(
                    "The worker stopped after reaching its resource limit.", "resource_limit"
                ) from exc
            if not message["ok"]:
                raise MathError(message["message"], message["code"])
            return MathResult.model_validate(message["result"])
        finally:
            if process.pid is not None:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
            receive.close()
            send.close()
            self._slots.release()

    async def acalculate(self, request: MathRequest | dict) -> MathResult:
        return await asyncio.to_thread(self.calculate, request)
