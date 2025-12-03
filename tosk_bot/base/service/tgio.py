import asyncio
import base64
import hashlib
import logging
from typing import Any, Awaitable, Callable

import httpx
from pydantic import AnyUrl, BaseModel
from teleapi.httpx_transport import httpx_teleapi_factory_async
from teleapi.teleapi import Update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Timeout = int
Limit = int
APIMethod = str
ParameterName = str


def tokenhash(token: str) -> str:
    """
    Generate a URL-safe base64-encoded SHA-256 hash of a token string.

    Args:
        token: The token string to be hashed.

    Returns:
        A URL-safe base64-encoded representation of the SHA-256 hash digest.
    """
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    urlsafe = base64.urlsafe_b64encode(digest).decode("utf-8")
    return urlsafe


class Response(BaseModel):
    """
    Represents an outgoing response from the bot.

    Attributes:
        method: The name of the Telegram Bot API method called.
        contents: The JSON-serializable payload returned by the API call.
    """

    # TODO validate method names via pydantic/dirty-teleapi?
    method: str
    # TODO use type annotation "JSON-serializable"?
    contents: Any


Handler = Callable[[Update | Response], Awaitable[None]]


class Input:
    """
    Handles receiving and processing incoming updates asynchronously.

    Attributes:
        teleapi: Async API client initialized with the token.
        timeout: Timeout for API operations.
        handler: Async callable to process Update objects.
        upd_queue: Asyncio queue holding incoming updates.
        n_workers: Number of async worker tasks processing updates.
    """

    def __init__(
        self,
        token: str,
        handler: Handler,
        timeout: Timeout = 10,
        limit: Limit = 128,
        queue_size: int = 512,
        workers: int = 1,
    ) -> None:
        """
        Initialize the Input handler.

        Args:
            token: API token for authentication.
            handler: Async callable to handle individual Update objects.
            timeout: Timeout for API calls (seconds).
            limit: Maximum number of updates to fetch at once.
            queue_size: Maximum size of update queue.
            workers: Number of concurrent worker tasks.
        """
        self.teleapi = httpx_teleapi_factory_async(token, timeout=timeout)
        self.timeout = timeout
        self.limit = limit
        self.handler = handler
        # TODO switch to aiodiskqueue
        self.upd_queue = asyncio.Queue(maxsize=queue_size)
        self.n_workers = workers
        logger.info(f"User input handler created with token_hash = {tokenhash(token)}")

    async def worker(self, name: str = "input") -> None:
        """
        Asynchronous worker coroutine that continuously processes updates from the queue.

        Processes updates by calling the handler. Runs indefinitely until cancelled.

        Args:
            name: Optional worker identifier for logging.
        """
        try:
            while True:
                try:
                    upd = await asyncio.wait_for(self.upd_queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    logger.debug(f"No updates awailable for worker '{name}'")
                    continue
                logger.debug(f"Input worker '{name}' got an update from a queue")
                await self.handler(upd)
                self.upd_queue.task_done()
        finally:
            logger.info(f"Cancelled an Input worker '{name}'")

    async def handle(
        self,
        notify_event: asyncio.Event | None = None,
    ) -> None:
        """
        Start worker tasks and fetch new updates continuously from Telegram.

        Fetches updates with getUpdates API, queues them for processing.
        If queue is full, updates are discarded. Optionally sets notification event
        when workers have started.

        Args:
            notify_event: Optional asyncio.Event to signal when workers have started.
        """
        # TODO ensure in-order updates with n_workers >= 1
        offset = 0
        async with asyncio.TaskGroup() as task_group:
            for i in range(self.n_workers):
                task_group.create_task(self.worker(f"input {i}"))
            if notify_event is not None:
                notify_event.set()
            try:
                while True:
                    updates = await self.teleapi.getUpdates(
                        offset=offset,
                        timeout=self.timeout,
                        limit=self.limit,
                    )
                    # having a list of situations when this can happen would be nice
                    if updates is None:
                        continue
                    updates = list(updates)
                    nupd = len(updates)
                    logger.info(f"Got {nupd} incoming update{'s' if nupd != 1 else ''}")
                    updates = sorted(updates, key=lambda u: u.update_id)

                    for update in updates:
                        try:
                            await asyncio.wait_for(
                                self.upd_queue.put(update), timeout=1
                            )
                            logger.debug("Input instance has put an update in queue")
                        except asyncio.TimeoutError:
                            # last resort is discarding updates
                            logger.error(
                                f"Input queue is full, discarding incoming update {update.update_id}"
                            )
                        offset = update.update_id + 1
                        # TODO handle int32 overflow???
            finally:
                logger.info("Cancelling input handling")


APIMethodWithPayload = tuple[APIMethod, dict[ParameterName, Any]]
Updater = Callable[
    [Timeout, Limit],
    Awaitable[list[APIMethodWithPayload]],
]


class Output:
    """
    Handles sending outgoing updates asynchronously via teleapi methods.

    Attributes:
        teleapi: Async API client initialized with the bot token.
        timeout: Timeout for API operations.
        upd_queue: Asyncio queue holding outgoing method-payload pairs to send.
        response_queue: Optional queue to send asynchronous responses to.
        n_workers: Number of concurrent worker tasks sending updates.
    """

    def __init__(
        self,
        token: str,
        response_queue: asyncio.Queue[Response] | None = None,
        timeout: Timeout = 10,
        limit: Limit = 128,
        queue_size: int = 512,
        workers: int = 1,
    ) -> None:
        """
        Initialize the Output handler.

        Args:
            token: API token for the Telegram bot.
            response_queue: Optional asyncio.Queue to receive API call responses.
            timeout: Timeout for API requests (seconds).
            limit: Maximum number of outgoing updates to fetch.
            queue_size: Max size of internal outgoing update queue.
            workers: Number of concurrent worker tasks.
        """
        self.teleapi = httpx_teleapi_factory_async(token, timeout=timeout)
        self.timeout = timeout
        self.limit = limit
        self.response_queue = response_queue
        # TODO switch to aiodiskqueue
        self.upd_queue = asyncio.Queue(maxsize=queue_size)
        self.n_workers = workers
        logger.info(f"Bot output handler created with token_hash = {tokenhash(token)}")

    async def worker(self, name: str = "output") -> None:
        """
        Async worker coroutine that continually sends updates from the queue using teleapi.

        Catches and logs HTTP and unexpected exceptions. If a response_queue is provided,
        API responses are sent there asynchronously.

        Args:
            name: Optional worker identifier for logging.
        """
        try:
            while True:
                # TODO implement and use dirty-teleapi models
                method, payload = await self.upd_queue.get()
                logger.debug(f"Output worker '{name}' got an update from a queue")
                try:
                    response = await getattr(self.teleapi, method)(payload)
                except httpx.HTTPStatusError as e:
                    logger.error(f"Teleapi/{method} HTTP status error: {e}")
                except httpx.RequestError as e:
                    logger.error(f"Teleapi/{method} HTTP request error: {e}")
                except Exception as e:
                    logger.error(f"Teleapi/{method} unexpected error: {e}")
                if self.response_queue is not None:
                    try:
                        await asyncio.wait_for(
                            self.response_queue.put(
                                Response(
                                    method=method,
                                    contents=response,
                                )
                            ),
                            timeout=1,
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Response queue is full, discarding {method}'s response"
                        )
                self.upd_queue.task_done()
        finally:
            logger.info(f"Cancelled an Output worker '{name}'")

    async def request(self, method: str, payload: Any) -> None:
        # TODO pydantic models for payloads
        await self.upd_queue.put((method, payload))

    async def handle(
        self,
        notify_event: asyncio.Event | None = None,
    ) -> None:
        """
        Start worker tasks and send outgoing updates from `upd_queue`.

        This coroutine launches concurrent worker tasks that consume method-payload pairs
        from an internal outgoing queue and send them using teleapi client.

        Args:
            notify_event: Optional asyncio.Event to signal when workers have started.

        Behavior:
            - Requires external code to fill `upd_queue`.
            - Runs indefinitely until cancelled.
        """
        # TODO ensure in-order updates with n_workers >= 1
        async with asyncio.TaskGroup() as task_group:
            for i in range(self.n_workers):
                task_group.create_task(self.worker(f"output {i}"))
            if notify_event is not None:
                notify_event.set()
