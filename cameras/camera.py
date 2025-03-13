import cv2
import numpy as np
from serial import *
import socket
import time
import threading
import copy
from ctypes import *
from io import BytesIO

from pypylon import pylon,genicam
import json
import pickle

import sys
sys.path.append("libs/MVSImport")
from MvCameraControl_class import *
from CamOperation_class import *

def ToHexStr(num):
    chaDic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
    hexStr = ""
    if num < 0:
        num = num + 2**32
    while num >= 16:
        digit = num % 16
        hexStr = chaDic.get(digit, str(digit)) + hexStr
        num //= 16
    hexStr = chaDic.get(num, str(num)) + hexStr   
    return hexStr

def load_webcam_feature(cap:cv2.VideoCapture, path):
    feature = open(path, "r").read().split(",")
    width = int(feature["width"])
    height = int(feature["height"])
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

class Camera():
    NO_ERROR = "NoError"
    BASLER = "Basler"
    WEBCAM = "Webcam"
    HIK = "HIK"
    def __init__(self, config=None):
        super(Camera,self).__init__()
        self._bLive = False
        self._cap = None
        self._mat = None

        self._stFrameInfo = MV_FRAME_OUT_INFO_EX()
        self._grab_result = None
        self._error = Camera.NO_ERROR
        self._dtype = self.WEBCAM
        # id: 0, 1, 2, 3 for WEBCAM
        # Serinumber for Basler
        # if null, open first device
        self._id = "0"
        self._name = "Camera"
        self._feature_file = ""
        self._use_feature = False
        self._is_color = True
        self._is_open = False

        self._disable_calib = False
        self._calib_coef:list = None
        self._resize:int = None
        if config:
            self.set_config(config=config)
    @property
    def error(self):
        return self._error
    
    @property
    def name(self):
        return self._name

    def set_enabled_calib(self, b:bool):
        self._disable_calib = not b

    def get_enabled_calib(self):
        return not self._disable_calib

    def set_config(self,config):
        self._dtype = config.get("dtype", "Webcam")
        self._id = config.get("id", "")
        self._is_color = config.get("color", False)
        self._name = config.get("name", "Camera")

        feature = config.get("feature", None)

        if feature:
            self._feature_file = feature
            self._use_feature = True

        resize = config.get("resize", None)
        if resize is not None:
            if isinstance(resize, int):
                self._resize = (resize, resize)
            else:
                self._resize = tuple(resize)

        calib = config.get("calib", None)
        if calib:
            try:
                with open(calib, "rb") as file:
                    self._calib_coef = pickle.load(file)
                    file.close()
            except Exception as ex:
                print("load calib file failed: ", ex)
                self._calib_coef = None
    @staticmethod
    def resize(mat, new_size:int):
        if isinstance(new_size, int):
            new_size = (new_size, new_size)
        w, h = new_size
        rw, rh = w / mat.shape[1], h / mat.shape[0]
        r = min(rw, rh)
        new_w = int(mat.shape[1] * r)
        new_h = int(mat.shape[0] * r)

        if new_w > mat.shape[1]:
            mode = cv2.INTER_CUBIC
        else:
            mode = cv2.INTER_AREA

        return cv2.resize(mat, (new_w, new_h), interpolation=mode)

    def undistort_image(self, mat, calib_coef):
        '''
        mapx, mapy, roi: init_map 
        '''
        _, _, _, mapx, mapy, roi = calib_coef

        t0 = time.time()
        dst = cv2.remap(mat, mapx, mapy, cv2.INTER_LINEAR)
        dt = time.time() - t0

        t0 = time.time()
        x, y, w, h = roi
        dst = dst[y:y+h, x:x+w]
        dt = time.time() - t0

        return dst

    @staticmethod
    def getHIKDevices():
        list_devinfo = MV_CC_DEVICE_INFO_LIST()
        tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, list_devinfo)
        # if ret != 0:
        #     print('enum devices fail! ret = '+ ToHexStr(ret))
        # else:
        #     print('find %d device!'%list_devinfo.nDeviceNum)           
        device_names = {}
        for i in range(0, list_devinfo.nDeviceNum):
            mvcc_dev_info = cast(list_devinfo.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                # print("\ngige device: [%d]" % i)
                strModeName = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                    strModeName = strModeName + chr(per)
                # print("device model name: %s" % strModeName)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)

                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                # print("current ip: %d.%d.%d.%d\n" % (nip1, nip2, nip3, nip4))
                name = "Gige["+str(i)+"]:"+str(nip1)+"."+str(nip2)+"."+str(nip3)+"."+str(nip4)
                device_names[strSerialNumber] = name
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                # print("\nu3v device: [%d]" % i)
                strModeName = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName:
                    if per == 0:
                        break
                    strModeName = strModeName + chr(per)
                # print("device model name: %s" % strModeName)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)
                # print("user serial number: %s" % strSerialNumber)
                if strModeName.startswith("ac"):
                    name = f"Basler USB3[{i}]-[{strModeName}]-[{strSerialNumber}]"
                else:
                    name = f"HIK USB3[{i}]-[{strModeName}]-[{strSerialNumber}]"
                device_names[strSerialNumber] = name
        return device_names, list_devinfo
        #
    @staticmethod
    def getBaslerDevices():
        devs = {}
        devices = pylon.TlFactory.GetInstance().EnumerateDevices()
        for dev in devices:
            devs[dev.GetSerialNumber()] = dev
        return devs
    
    @property
    def cap(self):
        return self._cap
    
    @cap.setter
    def cap(self, value):
        self._cap = value
        
    @property
    def mat(self):
        return self._mat

    def start(self): 
        if self._bLive:
            return
        self._bLive = True
        threading.Thread(self.loop_live_cam).start()

    def stop(self): 
        self._bLive = False

    def reset(self):
        if self.is_open():
            self.close()
        self.open()

    def loop_live_cam(self):
        while self._bLive:
            self._mat = self.grab()

            if self._mat is not None:
                time.sleep(0.001)
        
    def is_open(self):
        return self._is_open
    
    def is_live(self):
        return self._bLive

    def open(self):
        self._is_open = False
        self._error = Camera.NO_ERROR

        if self._dtype == self.WEBCAM:
            if not self._id or not self._id.isdigit():
                self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            else:
                self.cap = cv2.VideoCapture(int(self._id), cv2.CAP_DSHOW)
            self._is_open = self.cap.isOpened()
            if self._is_open:
                self.cap.set(cv2.CAP_PROP_FPS, 30.)
            # try reading nodeMap
            if self._use_feature:
                try:
                    load_webcam_feature(self.cap, self._feature_file)
                except Exception as ex:
                    self._error = str(ex)

        elif self._dtype == self.BASLER:
            basler_devices = self.getBaslerDevices()
            if not len(basler_devices):
                pass
            else:
                try:
                    if self._id in basler_devices:
                        dev = basler_devices[self._id]
                        self.cap = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(dev))
                    elif self._id.isdigit():
                        index = int(self._id)
                        key = list(basler_devices.keys())[index]
                        dev = basler_devices[key]
                        self.cap = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(dev))
                    else:
                        self.cap = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
                    
                    self.cap.Open()
                    self._is_open = self.cap.IsOpen()
                    # try reading nodeMap
                    if self._use_feature:
                        try:
                            # nodeFile = "acA1920-150um_40044700_MaxSize1.pfs"
                            pylon.FeaturePersistence.Load(self._feature_file, self.cap.GetNodeMap(), True)
                        except Exception as ex:
                            self._error = str(ex)
                        #
                    if self._is_color:
                        self.converter = pylon.ImageFormatConverter()
                        # converting to opencv bgr format
                        self.converter.OutputPixelFormat = pylon.PixelType_BGR8packed
                        self.converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

                    if self.cap.IsOpen():
                        self.cap.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
                except Exception as ex:
                    self._error = str(ex)
                    self.cap = None    

        elif self._dtype == self.HIK:
            device_names, device_infoes = Camera.getHIKDevices()
            # by serinumber
            if self._id in device_names:
                idevice = list(device_names.keys()).index(self._id)
            # by index 0, 1
            elif self._id.isdigit():
                idevice = int(self._id)
            # fisrt device
            else:
                idevice = 0
            try:
                key = list(device_names.keys())[idevice]
                self._name = device_names[key]
                self.cap = CameraOperation(MvCamera(), device_infoes, idevice)

                ret = self.cap.Open_device()
                if 0 != ret:
                    self._error = "Camera open failed"
                else:
                    if self._use_feature:
                        ret = self.cap.obj_cam.MV_CC_FeatureLoad(self._feature_file)
                        if 0 != ret:
                            self._error = "Camera Load feature failed"

                    self.cap.Start_grabbing()
                    self._is_open = True
                    
            except IndexError as ex:
                self._error = "Camera index out of range. Num cameras found : %d" % len(device_names)
            except Exception as ex:
                self.cap = None    
                self._error = str(ex)
        else:
            self.cap = None

    def close(self):
        self.stop()
        time.sleep(0.1)
        try:
            if self.is_open():
                if self._dtype == self.WEBCAM:
                    self.cap.release()
                elif self._dtype == self.BASLER:
                    self.cap.StopGrabbing()
                    if self._grab_result is not None:
                        self._grab_result.Release()
                    self.cap.Close()
                elif self._dtype == self.HIK:
                    self.cap.Stop_grabbing()
                    self.cap.Close_device()
                self._is_open = False
            
            self._mat = None
            return True
        except Exception as ex:
            self._error = str(ex)
            return False

    def grab(self):
        _mat = None
        self._error = Camera.NO_ERROR
        # t_start = time.time()
        try:
            if self._dtype == self.WEBCAM:
                ret, _mat = self.cap.read()
                if not ret:
                    self._error = "Camera grab fail"
                    self.stop()
                else:
                    pass

            elif self._dtype == self.BASLER:
                    self._grab_result = self.cap.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
                    if self._grab_result.GrabSucceeded():
                        if self._is_color:
                            image = self.converter.Convert(self._grab_result)
                            _mat = image.GetArray()
                        else:
                            _mat = self._grab_result.Array
                    else:
                        self._error = "Camera grab fail"
                        self.stop()
            elif self._dtype == self.HIK:  
                # 
                ret = self.cap.obj_cam.MV_CC_GetOneFrameTimeout(byref(self.cap.buf_cache), self.cap.n_payload_size, self._stFrameInfo, 1000)
                if ret == 0:
                    img_buff = None
                    self.cap.st_frame_info = self._stFrameInfo
                    self.cap.n_save_image_size = self.cap.st_frame_info.nWidth * self.cap.st_frame_info.nHeight * 3 + 2048
                    if img_buff is None:
                        img_buff = (c_ubyte * self.cap.n_save_image_size)()
            
                    if PixelType_Gvsp_Mono8 == self.cap.st_frame_info.enPixelType:
                        _mat = CameraOperation.Mono_numpy(self.cap,self.cap.buf_cache,self.cap.st_frame_info.nWidth,self.cap.st_frame_info.nHeight)
                    
                    elif PixelType_Gvsp_BayerGB8 == self.cap.st_frame_info.enPixelType:
                        numArray = CameraOperation.Mono_numpy(self.cap,self.cap.buf_cache,self.cap.st_frame_info.nWidth,self.cap.st_frame_info.nHeight)
                        _mat = cv2.cvtColor(numArray,cv2.COLOR_BAYER_GB2RGB)
                    
                    elif PixelType_Gvsp_BayerRG8 == self.cap.st_frame_info.enPixelType:
                        numArray = CameraOperation.Mono_numpy(self.cap,self.cap.buf_cache,self.cap.st_frame_info.nWidth,self.cap.st_frame_info.nHeight)
                        _mat = cv2.cvtColor(numArray,cv2.COLOR_BAYER_RG2RGB)

                    elif PixelType_Gvsp_RGB8_Packed == self.cap.st_frame_info.enPixelType:
                        _mat = CameraOperation.Color_numpy(self.cap,self.cap.buf_cache,self.cap.st_frame_info.nWidth,self.cap.st_frame_info.nHeight)
                
                else:
                    self._error = "Camera grab fail"
                    self.stop()
                    _mat = None

        except Exception as ex:
            self._error = str(ex)
            _mat = None

        # dt = time.time() - t_start
        # print("dt grab image: ", dt)

        # t_start = time.time()

        if self._resize is not None and _mat is not None:
            _mat = self.resize(_mat, self._resize)
        
        # dt = time.time() - t_start
        # print("dt resize image: ", dt)

        # t_start = time.time()

        if self._calib_coef is not None and not self._disable_calib and _mat is not None:
            _mat = self.undistort_image(_mat, self._calib_coef)
        # 
        # dt = time.time() - t_start
        # print("dt calib image: ", dt)

        return _mat

if __name__ == "__main__":
    print(Camera.getHIKDevices())
    camera = Camera()
    camera.set_config({
        "dtype":"HIK",
        "id": "0"
    })

    camera.open()
    if camera.is_open():
        print("Camera is opened")
        camera.close()
    else:
        print("Camera open fail")
