from math import *
import math
from threading import Thread, Timer
from time import *
from tkinter.constants import X
from typing import Text
import cv2
from numba import jit
import tkinter as TK
from PIL import Image, ImageTk
from WindowRendererGroupPreview import WindowRendererGroupPreview
from WindowRendererPreview import WindowRendererPreview
from tkinter import messagebox
from cv2 import imshow, resize, INTER_NEAREST

from captureRunnerOnThread import CaptureRunnerOnThread
from windowCaptureHandler import WindowCapture

class WindowRenderer(): 
    title = "MCGI ADDPRO-TOOL : COMBINE ZOOM GALLERIES"
    width = 0
    height = 0
    captureRunnerOnThread = None
    countThreadRun = 0
    background  = (0,177,64)
    canvas = None
    currentImage = None
    captureFrame = None
    imageCellSize = None
    imageListInfo = None
    groupImageListInfo = []
    window = None

    currentCol = 0
    currentRow = 0
    currentIndex = 0
    renderPreviewWindow = None
    renderGroupPreviewWindow = None
    isRendering = False
    parent = None
    
    def __init__(self, parent, background, captureConfiguration):        
        self.initializeObject(parent, background, captureConfiguration)

    def initializeObject(self,parent, background, captureConfiguration):
        self.parent = parent
        try:
            self.window.focus_set()
            return
        except Exception:
            self.window = TK.Toplevel(self.parent)
            self.isRendering = False
            pass

        self.countThreadRun = 0;
        self.background = background
        self.window.title(self.title)
        self.window.attributes('-fullscreen', True)
        self.width = self.window.winfo_screenwidth()
        self.height = self.window.winfo_screenheight()
        self.captureConfiguration = captureConfiguration



        self.window.canvas = TK.Canvas(self.window, background=self.backgroundColorToStr(), highlightthickness=0)      
        self.window.canvas.pack(fill=TK.BOTH, expand=True) 
        self.window.canvasImageConfigId = self.window.canvas.create_image(self.width/2, self.height/2, image=None, anchor=TK.CENTER)    

        self.window.canvasTextConfigId = self.window.canvas.create_text(100, 100, text="",anchor=TK.NW)
        self.captureRunnerOnThread = CaptureRunnerOnThread(captureConfiguration, self.background).start()
        self.captureRunnerOnThread.startFramePool(self.background, self.width, 10)

        
        # self.window.buttonFrame = TK.Frame(self.window)
        # self.window.buttonFrame.place(x=self.window.buttonFrame.winfo_width(), y=0)
        self.window.fpsLable = TK.Label(self.window, text="FPS", background=self.backgroundColorToStr())
        #self.window.fpsLable.place(x=self.window.fpsLable.winfo_width(), y=0) #.grid(column=0, row=0) 
        # TK.Label(self.window.buttonFrame, text="MAIN GALLERY", relief=TK.FLAT).grid(column=0, row=0) #grid(row=1,column=1)
        # TK.Button(self.window.buttonFrame, text="OPEN GROUP PREVIEW", relief=TK.RAISED).grid(column=1, row=0) #grid(row=1,column=1)
        
        self.addContextMenu()
        
        self.window.bind('<Button-1>', self.windowClick)
        self.window.bind('<Button-3>', self.windowRClick)

        # self.window.bind('<FocusIn>', self.focusIn)
        # self.window.bind('<FocusOut>', self.focusOut)
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        # self.window.buttonFrame.after(5000, self.hideButtonPanel)

        #return self

    def on_closing(self):
        self.captureRunnerOnThread.stopFramePool()
        self.window.destroy()
        self.isRendering = False;


    # def hideButtonPanel(self):
    #     self.window.buttonFrame.place_forget()

    # def focusIn(self):
    #     print("focus in")
    #     self.window.buttonFrame.pack()
    #     messagebox.showinfo(title="focus in", message="focus in")

    def focusOut(self):
        print("focus Out")
        self.window.buttonFrame.pack_forget()
        messagebox.showinfo(title="focus Out", message="focus Out")


    def addContextMenu(self):
        self.window.menu = TK.Menu(self.window, tearoff=0)
        self.window.menu.add_command(label="Pin to Preview Window", command=self.menu_OpenToPreview)
        self.window.menu.add_command(label="Pin to New Preview Window", command=self.menu_Open)
        self.window.menu.add_separator()
        self.window.menu.add_command(label="Open Group Preview Window", command=self.menu_OpenGroupPreview)
        self.window.menu.add_command(label="Pin to Group Preview Window", command=self.menu_OpenToGroupPreview)
        self.window.menu.add_separator()
        self.window.menu.add_separator()
        self.window.menu.add_separator()
        self.window.menu.add_separator()
        self.window.menu.add_command(label="Clear Group Preview Window", command=self.menu_ClearGroupPreview)


    
    def render(self):
        self.initializeObject(self.parent, self.background, self.captureConfiguration)
        if(self.isRendering is False):
            self.window.after(1000, self.__runCapture)
            #t = Thread(target=self.__runCapture, daemon=True)
            #t.start()
            #t.join()


    #@jit
    def __runCapture(self): #(self):
        global prevFrmae
        
        try:
            
            seconds = 0.1
            #self.captureFrame = self.captureRunnerOnThread.start().frame
            buffLen = len(self.captureRunnerOnThread.framePool) 

            # if(buffLen < 10):
            #     Thread(target=self.buffAhead30Frames, daemon=True).start()

            #while len(self.captureRunnerOnThread.framePool) > 0:
            start = time()
            
            self.imageCellSize = self.captureRunnerOnThread.uniformSize
            self.imageListInfo = self.captureRunnerOnThread.imageListInfo

            #self.window.cvImage = self.captureFrame
            #captureImage = self.openCVImageToTkImage(self.captureFrame, (self.width, 0))
            #self.window.background = captureImage
            self.captureFrame = self.captureRunnerOnThread.framePool[0]
            #self.captureFrame = self.captureRunnerOnThread.pilStart(self.background, self.width).pilFrame
            self.window.background = self.captureFrame
            self.window.canvas.itemconfig(self.window.canvasImageConfigId, image = self.window.background )
            prevFrmae = self.window.background 
            #self.window.canvasImageConfigId = self.window.canvas.create_image(self.width/2, self.height/2, image=self.window.background, anchor=TK.CENTER)    

            self.countThreadRun +=1
            #if(len(self.captureRunnerOnThread.framePool) > 1):

            end = time()
            seconds = end - start
            if(seconds == 0):
                seconds = 0.1
            #print ("ON THREAD_______________", self.countThreadRun,  f"FPS: {1/seconds}" )
            #self.window.fpsLable.config(text = "FPS: {0}, BuFF: {1}".format(int(1/seconds), buffLen))
            #cv2.imshow("preview", self.window.cvImage)
            #print("+ len(self.captureRunnerOnThread.framePool)", len(self.captureRunnerOnThread.framePool))
            print("frmaeCreateionTime: ", self.captureRunnerOnThread.frmaeCreateionTime)
            self.countThreadRun +=1

            if(len(self.captureRunnerOnThread.framePool) > 1):
                self.captureRunnerOnThread.framePool.pop(0)

            
                    

        except Exception as e: 
            #captureImage = self.captureRunnerOnThread.startNoThread().frame
            #captureImage = self.openCVImageToTkImage(captureImage, (self.width, 0))
            #self.window.background = captureImage
            #self.window.canvas.itemconfig(self.window.canvasImageConfigId, image = captureImage)

            print ("ERROR!!!", e)
            pass

        self.isRendering = True
        #if(self.renderGroupPreviewWindow is not None and self.renderGroupPreviewWindow.isRendering is True):
        #    self.window.after(200, self.__runCapture)
            #print("sched 300 MS")
        #else:
        #    self.window.after(1, self.__runCapture)
            #print("sched 1 MS")
        #self.window.after(math.floor(self.captureRunnerOnThread.frmaeCreateionTime * 1000), self.__runCapture)
        #t = Timer(interval= self.captureRunnerOnThread.frmaeCreateionTime, function=self.__runCapture)
        #t = Timer(interval= 0.001, function=self.__runCapture)
        #t = Thread(target=self.__runCapture,daemon=True)
        #t.setDaemon(True)
        #t.start()
        self.window.after(5, self.__runCapture)


    def buffAhead30Frames(self):
        for i in range(1):
            self.captureRunnerOnThread.startFramePoolWorkExtraFrame()

    #@jit
    def resizeCVImage(self, img, size= (0,0)):
        _height, _width, _ = img.shape

        #size ->> width height
        new_width = size[0]
        new_height = size[1]

        if new_width == 0 and new_height == 0:
            return img

        dim = self.getAspectRation((_width, _height), size)

        return resize(img, dim, interpolation=INTER_NEAREST) #img.resize(dim, Image.ANTIALIAS)


    #@jit
    def getAspectRation(self, size1,size2= (0,0)):
        _width = size1[0]
        _height = size1[1]

        #size ->> width height
        new_width = size2[0]
        new_height = size2[1]

        if new_width == 0 and new_height == 0:
            return size1
        if new_width == 0:
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
            img = Image.fromarray(self.resizeCVImage(imRGB, size))
        else:
            img = WindowCapture.newBlankImageSize(self.getAspectRation((10,10, size)), self.background)
            img = Image.fromarray(img)
        return ImageTk.PhotoImage(image=img)

    #@jit
    def backgroundColorToStr(self):
        return "#%02x%02x%02x" % self.background  

    def getInageCoordinates(self, x, y):
        mouseX, mouseY = x, y
        width_Unit, height_Unit = self.getAspectRation((self.captureFrame.width(),self.captureFrame.height()), (self.width, 0))
        #col, row, imageListCount, imageList
        cols,rows, count, images = self.imageListInfo
        offset_MouseY = mouseY - (self.height / 2 - height_Unit / 2)
        col_width_Unit = width_Unit / cols
        row_height_Unit = height_Unit / rows

        self.currentCol = floor(mouseX / col_width_Unit)
        self.currentRow = floor(offset_MouseY / row_height_Unit)
        self.currentIndex = (self.currentRow  * cols) + self.currentCol


    # def showButtonFrame(self):
    #     self.window.buttonFrame.place(x=self.window.buttonFrame.winfo_width()/2, y=0)
    #     self.window.buttonFrame.after(5000, self.hideButtonPanel)

    def windowClick(self, event):
        #self.showButtonFrame()
        if self.captureFrame is None: 
            return
        
        self.getInageCoordinates(event.x, event.y)


    def windowRClick(self, event):
        #self.showButtonFrame()

        if self.captureFrame is None: 
            return

        self.getInageCoordinates(event.x_root, event.y_root)
        images = self.imageListInfo[3]

        if(self.currentRow >= 0  and self.currentIndex < len(self.imageListInfo[3])): 
            self.window.menu.tk_popup(event.x_root, event.y_root)


    def menu_OpenToPreview(self):
        #cv2.imshow("preview", images[ self.currentIndex ])
        if(self.renderPreviewWindow is None):
            self.renderPreviewWindow = WindowRendererPreview(self.window,"PREVIEW", self.background, self.imageListInfo, self.currentIndex)

        self.renderPreviewWindow.update(self.imageListInfo, self.currentIndex)
        self.renderPreviewWindow.render()


    def menu_OpenToGroupPreview(self):
        self.groupImageListInfo = self.captureRunnerOnThread.imageIndexes
        #self.captureRunnerOnThread.imageIndexes = self.groupImageListInfo
        if(self.currentIndex not in self.groupImageListInfo):
            self.groupImageListInfo.append(self.currentIndex)
      

        if(self.renderGroupPreviewWindow is None):
            self.renderGroupPreviewWindow = WindowRendererGroupPreview(self.window,"GROUP PREVIEW", self.background, self.captureRunnerOnThread)
        #self.renderGroupPreviewWindow = WindowRendererGroupPreview(self.window,"GROUP PREVIEW", self.background, self.captureRunnerOnThread)

        self.captureRunnerOnThread.setImageIndexes(self.groupImageListInfo)
        self.renderGroupPreviewWindow.update(self.background, self.captureRunnerOnThread)
        self.renderGroupPreviewWindow.render()
            
        print (self.groupImageListInfo)

    def menu_OpenGroupPreview(self):
        self.groupImageListInfo = self.captureRunnerOnThread.imageIndexes
        if(self.renderGroupPreviewWindow is None):
            self.renderGroupPreviewWindow = WindowRendererGroupPreview(self.window,"GROUP PREVIEW", self.background, self.captureRunnerOnThread)
        #self.renderGroupPreviewWindow = WindowRendererGroupPreview(self.window,"GROUP PREVIEW", self.background, self.captureRunnerOnThread)


        self.captureRunnerOnThread.setImageIndexes(self.groupImageListInfo)
        self.renderGroupPreviewWindow.update(self.background, self.captureRunnerOnThread)
        self.renderGroupPreviewWindow.render()
            
        print (self.groupImageListInfo)

    def menu_ClearGroupPreview(self):
        self.groupImageListInfo.clear()
        self.captureRunnerOnThread.imageIndexes.clear()
        #self.renderGroupPreviewWindow.update(self.background, self.captureRunnerOnThread)

    def menu_Open(self):
        messagebox.showinfo(title="Work in progress", message='not yet ready')

