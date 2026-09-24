"""Task worker entrypoint: `python -m worker.task_worker` (needs live Redis)."""

from worker.task_worker import main

if __name__ == "__main__":
    main()
