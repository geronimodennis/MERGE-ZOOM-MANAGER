from numba import jit
from threading import Thread
#import multiprocessing as mp
from numpy import hstack, vstack
cimport numpy as np
from math import floor, ceil, sqrt
from CaptureProcessor import CaptureProcessor
from windowCaptureHandler import WindowCapture
from cv2 import resize, INTER_NEAREST
from windowCaptureHandler import WindowCapture
from PIL import Image, ImageTk
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import *
#import cython

cdef class CaptureRunnerOnThread:

    cdef object _pilFrame;
    cpdef np.ndarray _frame #= None
    cpdef list _framePool
    cpdef bint _isStartFramePool
    cpdef np.ndarray _groupFrame #= None
    cpdef list _groupFramePool #= None
    cpdef bint _isStartGroupFramePool
    #stopped = False
    cdef object _capPorcessor #= None 
    cdef tuple _uniformSize
    cdef list _imageListInfo #= [0,0,0,[]]#col, row, imageListCount, imageList
    cdef list _groupImageListInfo #= [0,0,0]#col, row, imageListCount
    cdef list _imageIndexes #= []
    cdef int width
    cdef int background[3]
    cdef int treshholdFrameCount
    cdef float _frmaeCreateionTime

    cdef tuple chromaColorKey #= (0,0,0)
    cdef list captureConfiguration
    def __init__(self, _captureConfiguration, _chromaColorKey):
        self.width = 0
        self.background = (0,177,64)
        self._isStartFramePool = False
        self._isStartGroupFramePool = False
        self._framePool = []
        self._groupFramePool = []
        self.imageIndexes = []
        self.imageListInfo = [0,0,0,[]]
        self.groupImageListInfo = [0,0,0]
        self.captureConfiguration = _captureConfiguration
        self.treshholdFrameCount = 1000;
        #self.stopped = False
        self.chromaColorKey = _chromaColorKey
        self.initCapturePocessor()
        self._frmaeCreateionTime =0.1
        
    property frame:
        def __get__(self):
            return self._frame
        def __set__(self, value):
            self._frame = value


    property frmaeCreateionTime:
        def __get__(self):
            return self._frmaeCreateionTime
        def __set__(self, value):
            self._frmaeCreateionTime = value

    property pilFrame:
        def __get__(self):
            return self._pilFrame
        def __set__(self, value):
            self._pilFrame = value


    property framePool:
        def __get__(self):
            return self._framePool
        def __set__(self, value):
            self._framePool = value

    property groupFrame:
        def __get__(self):
            return self._groupFrame
        def __set__(self, value):
            self._groupFrame = value

    property groupFramePool:
        def __get__(self):
            return self._groupFramePool
        def __set__(self, value):
            self._groupFramePool = value


    property uniformSize:
        def __get__(self):
            return self._uniformSize
        def __set__(self, value):
            self._uniformSize = value

    property imageListInfo:
        def __get__(self):
            return self._imageListInfo
        def __set__(self, value):
            self._imageListInfo = value

    property groupImageListInfo:
        def __get__(self):
            return self._groupImageListInfo
        def __set__(self, value):
            self._groupImageListInfo = value

    property capPorcessor:
        def __get__(self):
            return self._capPorcessor
        def __set__(self, value):
            self._capPorcessor = value

    property imageIndexes:
        def __get__(self):
            return self._imageIndexes
        def __set__(self, value):
            self._imageIndexes = value




    def start(self):
        t = Thread(target=self.get, daemon=True);
        t.start()
        #t.join()
        return self

    def pilStart(self, background, imageWidth):
        self.width = imageWidth
        self.background = background
        t = Thread(target=self.getAndConvert, daemon=True);
        t.start()
        #t.join()
        return self

    def getAndConvert(self):
        self._frame = self.threadRunner()
        self._pilFrame = self.openCVImageToTkImage(self.frame, (self.width, 0))
        


    def startNoThread(self):
        #print("returning frame")
        self.frame = self.threadRunner()
        #print("returned frame", self.frame)
        return self

    def startFramePool(self, background, imageWidth, treshholdFrameCount = 1000):
        self.treshholdFrameCount = treshholdFrameCount
        self.width = imageWidth
        self.background = background
        #print("startFramePool treshholdFrameCount: {0} _framePool Count: {1}".format(treshholdFrameCount, len(self._framePool)))
        self._isStartFramePool = True
        Thread(target=self.startFramePoolWork, daemon= True).start()
        return self

    def startFramePoolWork(self):
        #print("startFramePoolWork pushing frames before", len(self._framePool))
        #self.frame = self.threadRunner()
        #captureImage = self.openCVImageToTkImage(self.frame, (self.width, 0))
        #self._framePool.append(captureImage)

        #self.startFramePoolWorkExtraFrame()
        #cdef int frames = len(self._framePool)
        while(len(self._framePool) <= self.treshholdFrameCount and self._isStartFramePool == True):
            self.startFramePoolWorkExtraFrame()
            #sleep(0.01)

        #print("startFramePoolWork pushing frames after", frames, "frames <= 5", frames < 5)
        if(self._isStartFramePool == True):
            #executor = ThreadPoolExecutor(3)
            #future = executor.submit(self.startFramePoolWorkExtraFrame)
            #future.result()
            t = Thread(target=self.startFramePoolWork, daemon= True)
            t.start()
            #t.join(.5)

    def startFramePoolWorkExtraFrame(self):
        start = time()
        self.frame = self.threadRunner()

        captureImage = self.openCVImageToTkImage(self.frame, (self.width, 0))
        self._framePool.append(captureImage)

        #print("startFramePoolWorkExtraFrame _framePool Current Count: {0}".format(len(self._framePool)))
        end = time()
        self.frmaeCreateionTime = end - start
        if(self.frmaeCreateionTime == 0):
            self.frmaeCreateionTime = 0.1

        return self

    def stopFramePool(self):
        self._isStartFramePool = False
        self._framePool.clear()

    #def startWithMultProcessing(self):
    #    #not yet working
    #    p = mp.Process(target=self.get)
    #    p.start()
    #    #p.join()
    #    return self

    def startGroupImages(self):
        t = Thread(target=self.getImages, daemon= True).start()
        #t.setDaemon(True)
        #t.start()
        #t.join()
        return self

    def startGroupImagesPool(self, background, imageWidth):
        self.width = imageWidth
        self.background = background
        #print("startFramePool")
        self._isStartGroupFramePool = True
        Thread(target=self.startGroupImagesWork, daemon= True).start()
        return self

    def startGroupImagesWork(self):
        #print("startFramePoolWork")
        try:
            #self._frame = self.threadRunner()
            self._groupFrame = self.threadRunnerForImageList()

            while(len(self._groupFramePool) <= self.treshholdFrameCount and self._isStartGroupFramePool == True):
                captureImage = self.openCVImageToTkImage(self._groupFrame, (self.width, 0))
                self._groupFramePool.append(captureImage)
                #sleep(0.01)

        #print("pushing group frame", len(self._groupFramePool), "self._isStartGroupFramePool", self._isStartGroupFramePool)
        except:
            pass

        if(self._isStartGroupFramePool == True):
            Thread(target=self.startGroupImagesWork, daemon= True).start()
            #return self

    def stopGroupImagesPool(self):
        self._isStartGroupFramePool = False
        self._groupFramePool.clear()


    def get(self):
        self._frame = self.threadRunner()
        #cv2.imshow("ZOOM_GALLERY_MANAGER", self.frame)

    def getImages(self):
        try:
            self._frame = self.threadRunner()
            self._groupFrame = self.threadRunnerForImageList()
        except:
            pass
        #cv2.imshow("ZOOM_GALLERY_MANAGER", self.frame)

    def setImageIndexes(self, imageIndexes):
        self.imageIndexes = imageIndexes

    def stop(self):
        self.stopped = True

    
    def initCapturePocessor(self):
        if not self.capPorcessor:
            self.capPorcessor = CaptureProcessor(self.captureConfiguration, self.chromaColorKey)
        self.capPorcessor.setChromaKey(self.chromaColorKey)
        return self
    

    #@jit
    def threadRunner(self):
        cdef int col, row, counter #= 0, 0, 0
        cdef list rows, cols #= [], []
        rows = []
        cols = []
        
        self.initCapturePocessor()

        participants = self.capPorcessor.processScreenShot()
        participantCount = len(participants);
        sqrtParticipantCount = floor(sqrt(participantCount))

        self.imageListInfo[2] = participantCount
        self.imageListInfo[3] = participants

        if(participantCount > 0):

            col = self.imageListInfo[0]  = ceil(participantCount / sqrtParticipantCount) 
            row = self.imageListInfo[1] = ceil(participantCount / col)

            _imH,_imW,_ = participants[0].shape
            self.uniformSize = (_imW, _imH)
            blankImg = WindowCapture.newBlankImageSize(self.uniformSize, self.chromaColorKey)
            for r in range(row):
                cols = []
                
                # if(counter < participantCount):
                #     pass
                for c in range(col):
                    counter = (r  * col) + c
                    if(counter < participantCount):
                        _im = participants[counter]
                        cols.append(_im)
                        #counter +=1
                    else:
                        cols.append(blankImg)
                image_outer = hstack(cols)
                rows.append(image_outer)

            img = vstack(rows)
            return img
        else:
            return None

        
    #@jit
    def threadRunnerForImageList(self):
        cdef int col, row, counter #= 0, 0, 0
        cdef list rows, cols #= [], []
        rows = []
        cols = []

        self.initCapturePocessor()

        imageIdexes = self.imageIndexes
        participantCount = len(imageIdexes);
        sqrtParticipantCount = floor(sqrt(participantCount))

        participants = self.imageListInfo[3]
        self.groupImageListInfo[2] = participantCount
        

        if(participantCount > 0 and len(participants) > 0):

            col = self.groupImageListInfo[0]  = ceil(participantCount / sqrtParticipantCount) 
            row = self.groupImageListInfo[1] = ceil(participantCount / col)

            _imH,_imW,_ = participants[0].shape
            self.uniformSize = (_imW, _imH)
            blankImg = WindowCapture.newBlankImageSize(self.uniformSize, self.chromaColorKey)
            for r in range(row):
                cols = []
                #if(counter < participantCount):
                #    pass
                for c in range(col):
                    #self.currentIndex = (self.currentRow  * cols) + self.currentCol
                    counter = (r  * col) + c
                    if(counter < participantCount):
                        _im = participants[imageIdexes[counter]]
                        cols.append(_im)
                        #counter +=1
                    else:
                        cols.append(blankImg)

                image_outer = hstack(cols)
                rows.append(image_outer)

            img = vstack(rows)
            return img
        else:
            return None




    
    def resizeCVImage(self, img, size= (0,0)):
        _height, _width, _ = img.shape

        #size ->> width height
        new_width = size[0]
        new_height = size[1]

        if new_width is 0 and new_height is 0:
            return img

        dim = self.getAspectRation((_width, _height), size)

        return resize(img, dim, interpolation=INTER_NEAREST) #img.resize(dim, Image.ANTIALIAS)


    
    def getAspectRation(self, size1,size2= (0,0)):
        _width = size1[0]
        _height = size1[1]

        #size ->> width height
        new_width = size2[0]
        new_height = size2[1]

        if new_width is 0 and new_height is 0:
            return size1
        if new_width is 0:
            r = new_height / float(_height)
            dim = (int(_width * r), new_height)
        else:
            r = new_width / float(_width)
            dim = (new_width, int(_height * r))

        return dim

    
    def openCVImageToTkImage(self, cvImage, size = (0,100)):
        #result = self.frame
        try:
            if not cvImage is None: 
                imRGB = cvImage[:, :, ::-1]
                img = Image.fromarray(self.resizeCVImage(imRGB, size))
            else:
                img = WindowCapture.newBlankImageSize(self.getAspectRation((10,10, size)), (self.background[0], self.background[1], self.background[2]))
                img = Image.fromarray(img)

            return ImageTk.PhotoImage(image=img)
        except:
            return self.frame
        