"""Bounded process-pool execution and progress relay for independent treatment tasks."""




def _cpu_executor(worker_count: int):
    # h5py serializes HDF5 API calls within one process, so use spawned
    # processes for independent files. Spawn is also safe from server threads.
    import treatment_api as api

    return api.ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=api.get_context("spawn"),
    )


def _cpu_progress_callback(data_type: str, progress_queue):
    if progress_queue is None:
        return None
    last_reported = -1

    def report(current, total):
        nonlocal last_reported
        current, total = int(current), int(total)
        step = max(1, total // 100)
        if current == total or current == 1 or current - last_reported >= step:
            progress_queue.put((data_type, current, total))
            last_reported = current

    return report


def _run_parallel_cpu_jobs(items, worker, on_progress=None, on_complete=None, on_error=None):
    """Convert independent files in separate processes; relay progress to caller."""
    import treatment_api as api

    if not items:
        return {}
    worker_count = 1 if getattr(api._treatment_thread_context, 'parallel_sample', False) else api._treatment_worker_count(len(items))
    if worker_count == 1:
        class InlineProgress:
            def put(self, event):
                on_progress(event[0], *event[1:])

        results = {}
        for data_type, args in items.items():
            try:
                result = worker(data_type, *args, InlineProgress() if on_progress else None)
            except Exception as exc:
                if on_error:
                    on_error(data_type, exc)
                raise
            results[data_type] = result
            if on_complete:
                on_complete(data_type, result)
        return results

    manager_context = api.get_context("spawn").Manager() if on_progress else api.nullcontext(None)
    results = {}
    with manager_context as manager:
        progress_queue = manager.Queue() if manager else None

        def drain_progress():
            if progress_queue is None:
                return
            while True:
                try:
                    data_type, *progress = progress_queue.get_nowait()
                except api.Empty:
                    return
                on_progress(data_type, *progress)

        with api._cpu_executor(worker_count) as executor:
            futures = {
                executor.submit(worker, data_type, *args, progress_queue): data_type
                for data_type, args in items.items()
            }
            pending = set(futures)
            while pending:
                done, pending = api.wait(pending, timeout=0.02, return_when=api.FIRST_COMPLETED)
                drain_progress()
                for future in done:
                    data_type = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        if on_error:
                            on_error(data_type, exc)
                        raise
                    results[data_type] = result
                    if on_complete:
                        on_complete(data_type, result)
            drain_progress()
    return results
