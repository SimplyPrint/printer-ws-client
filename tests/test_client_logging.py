import uuid
from io import BytesIO, TextIOWrapper
import logging
import unittest
from logging.handlers import BaseRotatingHandler

from simplyprint_ws_client.client.config import Config

from simplyprint_ws_client.client.logging import ClientHandler
from simplyprint_ws_client.client.logging import ClientName

config = Config.get_blank()
config.unique_id = "test"
client_name = ClientName(config)


class FakeFileIO(TextIOWrapper):
    str_buffer: str

    def __init__(self, *args, **kwargs):
        super().__init__(BytesIO(), *args, **kwargs)
        self.str_buffer = ""

    def write(self, s: str) -> int:
        self.str_buffer += s
        return len(s)

    def read(self, __size: int = -1):
        return self.str_buffer

    def flush(self) -> None:
        pass

    def clear(self) -> None:
        self.str_buffer = ""


stream_output = FakeFileIO()
logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler(stream_output)])


class TestClientLogging(unittest.TestCase):
    def test_client_logging(self):
        root_logger = logging.getLogger()

        self.assertEqual(logging.root, root_logger)
        self.assertEqual(len(root_logger.handlers), 1)

        def assert_logger_handler(logger, parent, content):
            # Sort handlers to ClientHandlers are first
            # Just to easily check if the logger is correct
            logger.handlers.sort(key=lambda x: not isinstance(x, ClientHandler))

            self.assertEqual(logger.parent, parent)
            self.assertEqual(logger.propagate, False)
            self.assertEqual(len(logger.handlers), 2)
            self.assertTrue(isinstance(logger.handlers[0], BaseRotatingHandler))
            self.assertTrue(logger.handlers[0].delay)
            # Override the _open method to return the content
            setattr(logger.handlers[0], "_open", lambda: content)

        main_content = FakeFileIO()
        main_logger = logging.getLogger(client_name)
        assert_logger_handler(main_logger, root_logger, main_content)

        child_content = FakeFileIO()
        child_logger = main_logger.getChild("test")
        assert_logger_handler(child_logger, main_logger, child_content)

        child_content_2 = FakeFileIO()
        child_logger_2 = child_logger.getChild("test2")
        assert_logger_handler(child_logger_2, child_logger, child_content_2)

        # Ensure content goes to the correct loggers
        random_uuid = str(uuid.uuid4())

        child_logger.log(logging.DEBUG, random_uuid)
        self.assertTrue(random_uuid in stream_output.read())
        self.assertTrue(f'{random_uuid}\n' in child_content.read())
        self.assertEqual(main_content.read(), '')
        self.assertEqual(child_content_2.read(), '')
