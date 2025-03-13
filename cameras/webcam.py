from cameras.base_camera import *

import cv2
import yaml


class Webcam(BaseCamera):
    def __init__(self, config=None) -> None:
        super().__init__(config=config)

    def set_config(self, config):
        print("Set camera config")
        self._config = config
        self.create_device()

    def get_config(self):
        return self._config
    
    def get_error(self) -> str:
        return self._error
    
    def get_devices() -> dict:
        return {"0": 0, "1": 1, "2": 2, "3": 3}
    
    def load_feature(self, feature_path):
        '''
        feature: yaml file
        set width, height, ... of webcam
        '''
        feature = yaml.safe_load(open(feature_path, "r"))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, feature["width"])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, feature["height"])
        pass

    def create_device(self):
        devices = Webcam.get_devices()
        if not devices:
            self._error = ERR_NOT_FOUND_DEVICE
            return

        serinumber = self._config.get("id", 0)
        if serinumber in devices:
            key = serinumber
        else:
            key = None

        if key is not None:
            devInfo = devices[key]
            self._cap = cv2.VideoCapture(devInfo, cv2.CAP_DSHOW)
            self._model_name = f"Webcam_{devInfo}"
        else:
            self._cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            self._model_name = f"Webcam_0"
        

    def open(self) -> bool:
        _is_open = True
        self._error = NO_ERROR
        try:
            if not self._cap.isOpened():
                _is_open = False
            else:
                feature = self._config.get("feature", None)
                if feature:
                    try:
                        self.load_feature(feature=feature)
                    except Exception as ex:
                        self._error = ERR_LOAD_FEATURE_FAIL
        except Exception as ex:
            _is_open = False
            self._error = str(ex)
        return _is_open
    
    def close(self) -> bool:
        try:
            self._cap.release()
            return True
        except:
            return False
        
    def start_grabbing(self) -> bool:
        try:
            return True
        except:
            return False
        
    def stop_grabbing(self) -> bool:
        try:
            return True
        except:
            return False
        
    def grab(self):
        _mat = None
        ret, _mat = self._cap.read()
        if not ret:
            self._error = ERR_GRAB_FAIL
        
        return self._error, _mat