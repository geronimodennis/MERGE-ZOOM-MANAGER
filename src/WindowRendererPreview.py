import math
import threading
from time import *
import cv2
from numba import jit
import tkinter as TK
import numpy as np
from PIL import Image, ImageTk


from captureRunnerOnThread import CaptureRunnerOnThread
from windowCaptureHandler import WindowCapture

class WindowRendererPreview(): 
    xtitle = "MCGI ADDPRO-TOOL : {0}"
    title = ""
    width = 0
    height = 0
    background  = (0,177,64)
    imageListInfo = None
    parent = None
    window = None
    images = None
    captureFrame = None
    currentIndex = 0
    countThreadRun = 0
    isRendering = False
    windwowName=''

    
    def __init__(self, parent, title, background, imageListInfo, currentIndex):
        self.title = title
        self.parent = parent
        self.windwowName = self.xtitle.format(title)
        #cv2.namedWindow(self.windwowName, cv2.WND_PROP_FULLSCREEN)
        #cv2.setWindowProperty(self.windwowName, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

        try:
            self.window.focus_set()
            return
        except Exception:
            self.window = TK.Toplevel()
            #renderWindow = TK.Toplevel() #TK.Tk()
            pass

        self.currentIndex = currentIndex
        self.imageListInfo = imageListInfo
        self.images = self.imageListInfo[3]
        self.captureFrame = self.images[currentIndex]
        
        self.background = background
        self.window.title(self.windwowName)
        self.window.attributes('-fullscreen', True)
        self.width = self.parent.winfo_screenwidth()
        self.height = self.parent.winfo_screenheight()


        self.window.canvas = TK.Canvas(self.window, background=self.backgroundColorToStr(), highlightthickness=0)         
        self.window.canvas.pack(fill=TK.BOTH, expand=True) 

        self.captureFrame = self.images[self.currentIndex]
        self.window.cvImage = self.captureFrame
        self.window.captureImage = self.openCVImageToTkImage(self.captureFrame, (self.width, 0))
        self.window.canvasImageConfigId = self.window.canvas.create_image(self.width/2, self.height/2, image=self.window.captureImage , anchor=TK.CENTER)      
        
        self.window.fpsLable = TK.Label(self.window, text="FPS", background=self.backgroundColorToStr())
        self.window.fpsLable.place(x=self.window.fpsLable.winfo_width(), y=0) #.grid(column=0, row=0) 


    def update(self, imageListInfo, currentIndex):
        self.__init__(self.parent, self.title, self.background, imageListInfo, currentIndex)
    
    def render(self): #render(self, imageListInfo, currentIndex):   
        if(self.isRendering is False):    
            self.window.after(100, self.__runCapture)

        #threading.Thread(target=self.__runCapture).start()


    def __runCapture(self):
        global yPos
        #try:
        #global imageCellSize, imageListInfo, countThreadRun, captureFrame


        #try:
            
        start = time()
        self.images = self.imageListInfo[3]
        self.window.cvImage = self.images[self.currentIndex]
    
        #cv2.imshow(self.windwowName, self.openCVResize(self.cvImage, (self.width, 0)) )
        #cv2.waitKey(100)
        self.window.captureImage =self.openCVImageToTkImage(self.window.cvImage, (self.width, 0))
        self.window.canvas.itemconfig(self.window.canvasImageConfigId, image = self.window.captureImage)
        #self.window.canvas.update()
        end = time()
        seconds = end - start
        self.window.fpsLable.config(text = int(1/seconds))

        self.isRendering = True
        self.countThreadRun += 1


        print ("ON THREAD PREVIEW_______________", self.countThreadRun)
        self.countThreadRun +=1
        self.parent.after(100, self.__runCapture)
        self.window.after(100, self.__runCapture)

        #if(cv2.getWindowProperty(self.windwowName,cv2.WND_PROP_VISIBLE) >= 1):
        #    threading.Thread(target=self.__runCapture).start()
        #except:
        #    pass


        return self


    #@jit
    def resizeCVImage(self, img, size= (0,0)):
        _width, _height, _ = img.shape

        #size ->> width height
        new_width = size[0]
        new_height = size[1]

        if new_width is 0 and new_height is 0:
            return img

        dim = self.getAspectRation((_width, _height), size)

        return cv2.resize(dim, dim, interpolation=cv2.INTER_NEAREST)


    #@jit
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


    #@jit
    def openCVImageToTkImage(self, cvImage, size = (0,100)):
    
        if not cvImage is None: 
            imRGB = cvImage[:, :, ::-1]
            img = self.resizeCVImage(imRGB, size)
            img = Image.fromarray(imRGB)
        else:
            img = WindowCapture.newBlankImageSize(self.getAspectRation((10,10, size)), self.background)
            img = Image.fromarray(img)
        return ImageTk.PhotoImage(image=img)

    def openCVResize(self, cvImage, size = (0,100)):
    
        if not cvImage is None: 
            imRGB = cvImage[:, :, ::-1]
            img = self.resizeCVImage(imRGB, size)
            img = Image.fromarray(imRGB)
        else:
            img = WindowCapture.newBlankImageSize(self.getAspectRation((10,10, size)), self.background)
            img = Image.fromarray(img)
        return img

    #@jit(parallel=True)
    def backgroundColorToStr(self):
        return "#%02x%02x%02x" % self.background  

    

