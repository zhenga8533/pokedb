import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Empty, Queue

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class ThreadingManager:
    def __init__(self, threads: int, timeout: int, logger: object, retries: int = 3, backoff_factor: float = 0.3):
        """
        Initializes the threading manager with a shared queue, thread counts,
        and a requests session that supports retries.
        """

        self.threads = threads
        self.timeout = timeout
        self.logger = logger
        self.thread_counts = {}
        self.counter_lock = threading.Lock()
        self.queue = Queue()
        self.session = self.create_session(retries, backoff_factor)

    def create_session(self, retries: int, backoff_factor: float) -> requests.Session:
        """
        Create a persistent requests session with retry support.
        """

        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def add_to_queue(self, items: list):
        """
        Adds a list of items (each typically a dict with a URL and other metadata)
        to the shared queue.
        """

        for item in items:
            self.queue.put(item)

    def worker(self, thread_id: int, process_result_func: callable):
        """
        The generic worker method. It pulls items off the queue and hands them off to
        the given process_result_func for processing. Exceptions are caught and logged.
        """

        process_count = 0
        while True:
            try:
                result = self.queue.get(timeout=0.5)
            except Empty:
                break

            self.logger.log(logging.INFO, f"Thread {thread_id} processing: {result}")
            try:
                # The process_result_func is expected to handle one result,
                # using the shared session and timeout if needed.
                process_result_func(result, self.session, self.timeout, self.logger)
            except Exception as e:
                self.logger.log(logging.ERROR, f"Error processing result {result}: {e}")
            process_count += 1
            self.queue.task_done()

        self.logger.log(logging.INFO, f"Thread {thread_id} exiting. Processed {process_count} results.")
        with self.counter_lock:
            self.thread_counts[thread_id] = process_count

    def run_workers(self, process_result_func: callable):
        """
        Runs the worker threads via a ThreadPoolExecutor. The process_result_func parameter
        is a callback that defines how to process an individual result.
        """

        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(self.worker, i + 1, process_result_func) for i in range(self.threads)]
            for future in as_completed(futures):
                # Propagate any exceptions from the workers.
                future.result()

        self.logger.log(logging.INFO, "All threads have exited successfully.")
        total = sum(self.thread_counts.values())
        self.logger.log(logging.INFO, f"Total results processed: {total}.")
