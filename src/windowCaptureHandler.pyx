from numba.core.decorators import jit
import win32gui, win32ui, win32con
from win32api import GetSystemMetrics
import cv2
cimport numpy as np
import numpy as np
import tkinter as tk
from threading import Thread
from time import *

cdef class WindowCapture:

    # properties
    cdef int w #= GetSystemMetrics(0)
    cdef int h #= GetSystemMetrics(1)
    cdef str hwnd

    cdef long wDC
    cdef bytes signedIntsArray
    cdef object dcObj
    cdef object cDC
    cdef object dataBitMap
    cdef bint _isStartFramePool
    cdef list _framePool;

    # constructor
    def __init__(self, str hwnd = '', str window_name = ""):
        cdef int[4] window_rect 
        #try:
        self.w = GetSystemMetrics(0)
        self.h = GetSystemMetrics(1)
        self.dcObj = None
        self.cDC = None
        self.dataBitMap = None
        self._isStartFramePool = False
        self._framePool = [];

        if(hwnd == ''):
            self.hwnd = str(win32gui.FindWindow(None, window_name))
        else:
            self.hwnd = hwnd

        # get the window size
        window_rect = win32gui.GetWindowRect(self.hwnd)
        self.w = window_rect[2] - window_rect[0]
        self.h = window_rect[3] - window_rect[1]

        #except:
        #    self.hwnd = -1
        #    pass



    property framePool:
        def __get__(self):
            return self._framePool
        def __set__(self, value):
            self._framePool = value



    def startFramePool(self):
        if(self._isStartFramePool == False):
            self._isStartFramePool = True
            t = Thread(target=self.startFramePoolWork, daemon=True)
            t.start()

    def startFramePoolWork(self): 
        while len(self._framePool) <= 5:
        #if len(self._framePool) <= 30:
            #self._framePool.pop(len(self._framePool) -1)
            #self._framePool.pop(0) 
            self._framePool.append(self.get_screenshot())
            #sleep(10/1000)

        if(self._isStartFramePool == True):
            t = Thread(target=self.startFramePoolWork, daemon=True)
            t.start()
            #print("startFramePoolWork running")
        
        return self
        
    def stopFramePool(self):
        self._isStartCapturePool = False
        self._framePool.clear()
        print("startFramePool")

    def resetCapture(self, hwnd = "", window_name = ""):
        self.__init__(hwnd, window_name)
        # find the handle for the window we want to capture
        #cdef int[4] window_rect 
        #try:
        #if(hwnd == ''):
        #    self.hwnd = str(win32gui.FindWindow(None, window_name))
        #else:
        #    self.hwnd = hwnd

        # get the window size
        #window_rect = win32gui.GetWindowRect(self.hwnd)
        #self.w = window_rect[2] - window_rect[0]
        #self.h = window_rect[3] - window_rect[1]
        #except:
        #    self.hwnd = -1
        #    pass

    def get_screenshot(self):
        cdef np.ndarray img

        try:
            #self.freeResources()
            self.wDC = win32gui.GetWindowDC(self.hwnd)
            self.dcObj = win32ui.CreateDCFromHandle(self.wDC)
            self.cDC = self.dcObj.CreateCompatibleDC()
            self.dataBitMap = win32ui.CreateBitmap()
            self.dataBitMap.CreateCompatibleBitmap(self.dcObj, self.w, self.h)
            self.cDC.SelectObject(self.dataBitMap)
            self.cDC.BitBlt((0, 0), (self.w, self.h), self.dcObj, (0, 0), win32con.SRCCOPY)


            # save the screenshot
            self.signedIntsArray = self.dataBitMap.GetBitmapBits(True)
            img = np.fromstring(self.signedIntsArray, dtype='uint8').reshape((self.h, self.w, 4))
            self.freeResources()

            img = img[...,:3]
            img = np.ascontiguousarray(img)
            return img
        except Exception as e:
            print("ERROR in get_screenshot", e)
            self.freeResources()
            return self.newBlankImage()

    cdef freeResources(self):
        # Free Resources
        try:
            self.dcObj.DeleteDC()
            self.cDC.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, self.wDC)
            win32gui.DeleteObject(self.dataBitMap.GetHandle())
        except:
            pass

    @staticmethod
    def getScreeDimention():
        cdef int[2] ret = [GetSystemMetrics(0), GetSystemMetrics(1)]
        #ret['w'] = GetSystemMetrics(0);
        #ret['h'] =  GetSystemMetrics(1);
        return ret
    
    @staticmethod
    def newBlankImage(r=0,g=0,b=0):
        cdef int w = GetSystemMetrics(0)
        cdef int h = GetSystemMetrics(1)
        cdef np.ndarray img = np.zeros((h,w,3), np.uint8)
        # (B, G, R)
        img[:,0:h] = (b,g,r)
        img[:,0:w] = (b,g,r)
        img = img[...,:3]
        #img[:,w//2:w] = (0,255,0)
        return img

    @staticmethod
    #@jit
    def newBlankImageSize(tuple size = (0,0), tuple rbgChromaKey = (0,177,64)):
        cdef int w = GetSystemMetrics(0)
        cdef int h = GetSystemMetrics(1)
        cdef np.ndarray img = np.zeros((h,w,3), np.uint8)

        if(rbgChromaKey is None):
            rbgChromaKey = (0,177,64)

        h = size[0] #( hieght and Width )
        w = size[1]
        r,g,b = rbgChromaKey
      
        img = np.zeros((w,h,3), np.uint8)
        # (B, G, R)
        img[:,0:h] = (b,g,r)
        img[:,0:w] = (b,g,r)
        img = img[...,:3]
        #img[:,w//2:w] = (0,255,0)
        return img
