from numba import jit
from cv2 import inRange, findContours, approxPolyDP, boundingRect, copyMakeBorder, arcLength ,resize, RETR_TREE, CHAIN_APPROX_SIMPLE, BORDER_CONSTANT, INTER_NEAREST, INTER_LINEAR
#from numpy import array
from windowCaptureHandler import WindowCapture
cimport numpy as np
from threading import Thread

np.import_array()

class CaptureProcessor:
    _captureConfigurationList = []
    _chromaKey = (0,177,64)

    def __init__(self, list captureConfigurationList, chromaKey = _chromaKey):
        if(chromaKey is None):
            chromaKey = self._chromaKey
        r,g,b = chromaKey
        self._chromaKey = (b,g,r) 
        self._captureConfigurationList = captureConfigurationList



    #@jit(parallel=True)
    #@jit
    def processScreenShot(self, useSmallerCapture = False):

        cdef list mainList = []
        cdef list subList = []
        cdef int[2] dimSize = (0,0)
        cdef int borderSize =3
        cdef np.ndarray firstColorToMask
        cdef np.ndarray toMaskColor_lo
        cdef np.ndarray mask
        cdef np.ndarray screenshot, image
        cdef np.ndarray validImg
        cdef int x = 0
        cdef int y = 0
        cdef int w = 0
        cdef int h = 0 
        cdef np.ndarray contour
        cdef np.ndarray hierarchy
        cdef np.ndarray approx
        #cdef float aspectRatio = 0.0
        #cdef int borderSize =3
        #cdef list contours #, hierarchy, approx #,validImg, #*screenshot ,*image, *mask ,*firstColorToMask, *toMaskColor_lo

        #lowResFactor = 4
        
        for config in self._captureConfigurationList:
            captureHandler = config["captureHandler"]
            subList = []
            if captureHandler: #and len(captureHandler.framePool)>=1:
                #captureHandler.startFramePool()
                #print ("len(captureHandler.framePool)", len(captureHandler.framePool))
                #if(len(captureHandler.framePool)>=1):
                #image = screenshot = captureHandler.framePool[0]
                #captureHandler.framePool.pop(0)
                image = screenshot = captureHandler.get_screenshot()
                

                #sH, sW, _ = screenshot.shape
                #image = cv2.resize(screenshot, (int(sW / lowResFactor),int(sH / lowResFactor)))              
                #image =  screenshot #cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR) 
                #image2chroma = image.copy()

                #get the 1st pixel color of the image, for chroma masking
                firstColorToMask = image[0,0]
            
                #mask exact color
                toMaskColor_lo=firstColorToMask
                #toMaskColor_hi=np.array(firstColorToMask)

                # Mask the image
                mask=inRange(image,toMaskColor_lo,toMaskColor_lo)
                # Change image 
                
                #cv2.imwrite("mask.bmp", mask)
                contours, hierarchy = findContours(mask, RETR_TREE, CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    approx = approxPolyDP(contour, 0.01* arcLength(contour, True), True)

                    #find square or rectangle
                    if len(approx) == 4 :
                        x, y , w, h = boundingRect(approx)
                        #boundingBox = boundingRect(approx)

                        #aspectRatio = float(w / h)
                        #print(f'{x},{y},{w},{h}:  aspectRatio: ', aspectRatio)
                        if h >=50 and h <= 540: #aspectRatio >= 1.7   #and h >= 50 and h <= image.shape[0]/2: #and h >= (50 / lowResFactor) and h <= ((image.shape[0]/2)/lowResFactor) :  #(h >=50 and h <= 540):
                            validImg = copyMakeBorder(
                                image[y:y+h, x:x+w], 
                                #screenshot[y * lowResFactor: (y+h) * lowResFactor, x * lowResFactor : (x+w) * lowResFactor ],
                                borderSize, 
                                borderSize, 
                                borderSize, 
                                borderSize, 
                                BORDER_CONSTANT, 
                                value=self._chromaKey
                            )

                            #h, w, _ = validImg.shape
                            h = validImg.shape[0]
                            w = validImg.shape[1]

                            if(dimSize[0] is 0):
                                # width = w #int(w * 100 / 100)
                                # height = h #int(h * 100 / 100)
                                dimSize = (w, h)
                                #lst.append(validImg)
                            else:
                                #lst.append(cv2.resize(validImg, dimSize))
                                #print("dimSize", dimSize)
                                validImg = resize(validImg, dimSize, interpolation=INTER_LINEAR)
                            
                            subList.append(validImg)  
                            #del validImg

                if(len(subList) > 0):
                    subList = subList[::-1] #np.array(subList[::-1]) 
                    mainList = mainList + subList
                
                            
        return mainList

    def setChromaKey(self, chromaKey):
        if(chromaKey is None):
            chromaKey = self._chromaKey
        r,g,b = chromaKey
        self._chromaKey = (b,g,r)
