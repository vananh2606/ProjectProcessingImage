import sys 

sys.path.append("cameras")
from base_camera import *
from pypylon import pylon, genicam


class SODA(BaseCamera):
    def __init__(self, config=None) -> None:
        self._converter = None
        self._grab_result = None
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
        devs = {}
        devices = pylon.TlFactory.GetInstance().EnumerateDevices()
        for dev in devices:
            devs[dev.GetSerialNumber()] = dev
        return devs
    
    def create_device(self):
        devices = SODA.get_devices()

        if not devices:
            self._error = ERR_NOT_FOUND_DEVICE
            self._cap = None
            self._model_name = ""
            return
        
        if self._config is None:
            self._error = ERR_CONFIG_IS_NONE
            self._cap = None
            self._model_name = ""
            return

        serinumber = self._config.get("id", 0)

        if serinumber in devices:
            key = serinumber
        else:
            key = None

        if key is not None:
            devInfo = devices[key]
            self._cap = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(devInfo))
        else:
            self._cap = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
        
        self._model_name = self._cap.GetDeviceInfo().GetModelName()
        if not self.is_valid_model_name():
            self._error = ERR_MODEL_NAME
            self._cap = None
        else:
            self._error = NO_ERROR

    def open(self) -> bool:
        if self._cap is None:
            return False
        
        _is_open = True
        self._error = NO_ERROR

        try:
            self._cap.Open()
            if not self._cap.IsOpen():
                _is_open = False
            else:
                feature = self._config.get("feature", None)
                if feature:
                    try:
                        # nodeFile = "acA1920-150um_40044700_MaxSize1.pfs"
                        pylon.FeaturePersistence.Load(feature, self._cap.GetNodeMap(), True)
                    except Exception as ex:
                        self._error = ERR_LOAD_FEATURE_FAIL

            color = self._config.get("color", False)
            if color:       
                self._converter = pylon.ImageFormatConverter()
                # converting to opencv bgr format
                self._converter.OutputPixelFormat = pylon.PixelType_BGR8packed
                self._converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        except Exception as ex:
            _is_open = False
            self._error = str(ex)
        return _is_open
    
    def close(self) -> bool:
        try:
            self._cap.Close()
            return True
        except:
            return False
        
    def start_grabbing(self) -> bool:
        try:
            self._cap.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            return True
        except:
            return False
        
    def stop_grabbing(self) -> bool:
        try:
            self._cap.StopGrabbing()
            if self._grab_result is not None:
                self._grab_result.Release()
            return True
        except:
            return False
        
    def grab(self):
        _mat = None
        self._grab_result = self._cap.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
        if self._grab_result.GrabSucceeded():
            if self._converter:
                image = self._converter.Convert(self._grab_result)
                _mat = image.GetArray()
            else:
                _mat = self._grab_result.Array
        else:
            self._error = ERR_GRAB_FAIL
        
        return self._error, _mat