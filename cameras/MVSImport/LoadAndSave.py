# -- coding: utf-8 --

import sys

from ctypes import *

sys.path.append("cameras/MVSImport")
from MvCameraControl_class import *
# from cameras.MVSImport.MvCameraControl_class import *


def save_feature():
    deviceNames = []
    deviceList = MV_CC_DEVICE_INFO_LIST()
    tlayerType = MV_GIGE_DEVICE | MV_USB_DEVICE

    # ch:枚举设备 | en:Enum device
    ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
    if ret != 0:
        print("enum devices fail! ret[0x%x]" % ret)
        sys.exit()

    if deviceList.nDeviceNum == 0:
        print("find no device!")
        sys.exit()

    print("find %d devices!" % deviceList.nDeviceNum)

    for i in range(0, deviceList.nDeviceNum):
        mvcc_dev_info = cast(
            deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)
        ).contents
        if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
            print("\ngige device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                strModeName = strModeName + chr(per)
            print("device model name: %s" % strModeName)

            strSerialNumber = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                if per == 0:
                    break
                strSerialNumber = strSerialNumber + chr(per)

            nip1 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xFF000000) >> 24
            nip2 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00FF0000) >> 16
            nip3 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000FF00) >> 8
            nip4 = mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000FF
            print("current ip: %d.%d.%d.%d\n" % (nip1, nip2, nip3, nip4))

            name = f"{strModeName} {strSerialNumber}"
            deviceNames.append(name)

        elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
            print("\nu3v device: [%d]" % i)
            strModeName = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName:
                if per == 0:
                    break
                strModeName = strModeName + chr(per)
            print("device model name: %s" % strModeName)

            strSerialNumber = ""
            for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                if per == 0:
                    break
                strSerialNumber = strSerialNumber + chr(per)
            print("user serial number: %s" % strSerialNumber)
            name = f"{strModeName}-{strSerialNumber}"
            deviceNames.append(name)

    nConnectionNum = input("please input the number of the device to connect:")
    # nConnectionNum = 0

    if int(nConnectionNum) >= deviceList.nDeviceNum:
        print("intput error!")
        sys.exit()

    # ch:创建相机实例 | en:Creat Camera Object
    cam = MvCamera()

    # ch:选择设备并创建句柄 | en:Select device and create handle
    stDeviceList = cast(
        deviceList.pDeviceInfo[int(nConnectionNum)], POINTER(MV_CC_DEVICE_INFO)
    ).contents

    ret = cam.MV_CC_CreateHandle(stDeviceList)
    if ret != 0:
        print("create handle fail! ret[0x%x]" % ret)
        sys.exit()

    # ch:打开设备 | en:Open device
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print("open device fail! ret[0x%x]" % ret)
        sys.exit()

    print("start export the camera properties to the file")
    print("wait......")

    # ch:将相机属性导出到文件中 | en:Export the camera properties to the file

    path = "%s.ini" % deviceNames[int(nConnectionNum)]
    ret = cam.MV_CC_FeatureSave(path)
    if MV_OK != ret:
        print("save feature fail! ret [0x%x]" % ret)
    else:
        print("save feature success at %s" % path)
    print("finish export the camera properties to the file")

    print("start import the camera properties from the file")
    print("wait......")

    # ch:从文件中导入相机属性 | en:Import the camera properties from the file
    ret = cam.MV_CC_FeatureLoad(path)
    if MV_OK != ret:
        print("load feature fail! ret [0x%x]" % ret)
    print("finish import the camera properties from the file")

    # ch:关闭设备 | Close device
    ret = cam.MV_CC_CloseDevice()
    if ret != 0:
        print("close deivce fail! ret[0x%x]" % ret)
        sys.exit()

    # ch:销毁句柄 | Destroy handle
    ret = cam.MV_CC_DestroyHandle()
    if ret != 0:
        print("destroy handle fail! ret[0x%x]" % ret)
        sys.exit()


if __name__ == "__main__":
    save_feature()
