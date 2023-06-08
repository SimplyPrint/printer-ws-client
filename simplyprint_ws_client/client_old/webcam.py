from abc import abstractmethod
import base64
import logging
from typing import AsyncIterator, Optional

class WebcamException(Exception):
    """
    Exception raised when there is an error with the webcam.
    """
    pass

class Webcam:
    """
    Simple webcam class that can be used to capture images from a webcam.

    The intent is to either use this as-is or to subclass it and override it.
    """

    __IMAGE_SIZE = (1280, 720)
    __IMAGE_TYPE = "jpeg"
 
    __webcam_connected: bool = False

    @staticmethod
    def to_base64(data: bytes) -> str:
        """
        Converts a bytes object to a base64 string.
        """
        return base64.b64encode(data).decode()
    
    @property
    def connected(self) -> bool:
        """
        Returns whether the webcam is connected.
        """
        return self.__webcam_connected
    
    @connected.setter
    def connected(self, value: bool) -> None:
        """
        Sets whether the webcam is connected. Replace this with an actual check
        """
        self.__webcam_connected = value

    @abstractmethod
    def initialize_webcam(self) -> None:
        """
        Initializes the webcam.
        """
        raise WebcamException("Webcam not implemented")
    
    @abstractmethod
    async def snapshot(self) -> Optional[str]:
        """
        Takes a snapshot from the webcam and returns it as a base64 encoded string.
        """
        raise WebcamException("Webcam not implemented")
    
    @abstractmethod
    async def stream(self) -> AsyncIterator[str]:
        """
        Streams images from the webcam as base64 encoded strings.
        """
        raise WebcamException("Webcam not implemented")


class CV2Webcam(Webcam):
    __webcam: Optional[any] = None

    def initialize_webcam(self) -> None:
        try:
            import cv2
        except ImportError:
            raise WebcamException("OpenCV not installed, webcam will not be used")

        self.__webcam = cv2.VideoCapture(-1)
        self.webcam_connected = self.__webcam.isOpened()

    @property
    def connected(self) -> bool:
        return self.__webcam.isOpened()
    
    @connected.setter
    def connected(self, value: bool) -> None:
        if value:
            self.__webcam.open()
        else:
            self.__webcam.release()

    async def snapshot(self) -> Optional[str]:
        try:
            import cv2
        except ImportError:
            raise WebcamException("OpenCV is not installed but is required for webcam snapshots")

        max_width = self.__IMAGE_SIZE[0]
        max_height = self.__IMAGE_SIZE[1]

        _, frame = self.__webcam.read()

        if frame.shape[1] > max_width or frame.shape[0] > max_height:
            ratio = min(max_width / frame.shape[1], max_height / frame.shape[0])
            frame = cv2.resize(frame, (0, 0), fx=ratio, fy=ratio)

        _, buffer = cv2.imencode(".jpg", frame)

        return Webcam.to_base64(buffer.tobytes())
