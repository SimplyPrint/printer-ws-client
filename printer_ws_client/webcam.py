from typing import Dict

SNAPSHOT_ENDPOINT = "https://apirewrite.simplyprint.io/jobs/ReceiveSnapshot"

class WebcamSnapshot:
    def __init__(self, id: str, data: str):
        # Id of the image
        self.id: str = id
        # Base64 encoded image
        self.data: str = data
    
    def to_data(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "image": self.data
        }
