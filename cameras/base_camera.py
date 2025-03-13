from abc import ABC, abstractmethod
import numpy as np


NO_ERROR = ""
ERR_NOT_FOUND_DEVICE = "ERR_NOT_FOUND_DEVICE"
ERR_CREATE_DEVICE_FAIL = "ERR_CREATE_DEVICE_FAIL"
ERR_MODEL_NAME = "ERR_MODEL_NAME"
ERR_LOAD_FEATURE_FAIL = "ERR_LOAD_FEATURE_FAIL"
ERR_CONFIG_IS_NONE = "ERR_CONFIG_IS_NONE"
ERR_GRAB_FAIL = "ERR_GRAB_FAIL"


class BaseCamera(ABC):
    __MODEL_NAMES = ["SOD-ACA5472-08"]
    def __init__(self, config=None) -> None:
        super().__init__()
        self._error = NO_ERROR
        self._cap = None
        self._config = {}
        self._model_name = ""
        if config is not None:
            self.set_config(config)

    @abstractmethod
    def get_error(self) -> str: ...

    @abstractmethod
    def get_devices() -> dict: ...

    @abstractmethod
    def set_config(self, config): ...

    @abstractmethod
    def create_device(self): ...

    @abstractmethod
    def get_config(self): ...

    def is_valid_model_name(self) -> bool:
        # return self._model_name in BaseCamera.__MODEL_NAMES
        return True

    def get_model_name(self) -> str:
        return self._model_name

    @abstractmethod
    def open(self) -> bool: ...

    @abstractmethod
    def close(self) -> bool: ...

    @abstractmethod
    def start_grabbing(self) -> bool: ...

    @abstractmethod
    def stop_grabbing(self) -> bool: ...

    @abstractmethod
    def grab(self) -> tuple: ...

