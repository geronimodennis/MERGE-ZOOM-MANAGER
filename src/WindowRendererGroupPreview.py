from math import *
import math
from threading import Thread, Timer
from time import *
from numba import jit
import tkinter as TK
from PIL import Image, ImageTk
from tkinter import messagebox


from captureRunnerOnThread import CaptureRunnerOnThread
from windowCaptureHandler import WindowCapture

class WindowRendererGroupPreview(): 
    title = "MCGI ADDPRO-TOOL : {0}"
    width = 0
    height = 0
    background  = (0,177,64)
    captureRunnerOnThread = None
    groupImageListInfo = []
    parent = None
    window = None
    images = None
    captureFrame = None
    isRendering = False
    countThreadRun = 0
    
    def __init__(self, parent, title, background, captureRunnerOnThread):
        self.parent = parent
        #self.window = TK.Toplevel()
        try:
            self.window.focus_set()
            return
        except Exception:
            self.window = TK.Toplevel()
            #renderWindow = TK.Toplevel() #TK.Tk()
            #pass

  
        self.countThreadRun = 0
        self.background = background
        self.window.title(self.title.format(title))
        #self.window.state('zoomed')
        self.window.attributes('-fullscreen', True)

        self.width = self.window.winfo_screenwidth()
        self.height = self.window.winfo_screenheight()

        # self.width = self.window.winfo_screenwidth()
        # self.height = self.window.winfo_screenheight()

        self.captureRunnerOnThread = captureRunnerOnThread
        ##self.captureRunnerOnThread.startGroupImagesPool(background, self.width)

        self.window.canvas = TK.Canvas(self.window, background=self.backgroundColorToStr(), highlightthickness=0)         
        self.window.canvas.pack(fill=TK.BOTH, expand=True) 

        self.captureFrame = self.captureRunnerOnThread.startGroupImages().groupFrame
        #self.captureFrame = self.captureRunnerOnThread.groupFramePool[0]
        
        self.window.cvImage = self.captureFrame
        self.window.captureImage = self.openCVImageToTkImage(self.captureFrame, (self.width, 0))
        self.window.canvasImageConfigId = self.window.canvas.create_image(self.width/2, self.height/2, image=self.window.captureImage , anchor=TK.CENTER)      

        self.window.fpsLable = TK.Label(self.window, text="FPS", background=self.backgroundColorToStr())
        #self.window.fpsLable.place(x=self.window.fpsLable.winfo_width(), y=0) #.grid(column=0, row=0) 

        self.window.bind('<Button-1>', self.windowClick)
        self.window.bind('<Button-3>', self.windowRClick)

        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.addContextMenu()


    def addContextMenu(self):
        self.window.menu = TK.Menu(self.window, tearoff=0)
        self.window.menu.add_command(label="Remove From Pin", command=self.menu_RemoveFromPin)
        self.window.menu.add_separator()
        self.window.menu.add_separator()
        self.window.menu.add_separator()
        self.window.menu.add_separator()
        self.window.menu.add_command(label="Clear Group Preview Window", command=self.menu_ClearGroupPreview)



    def on_closing(self):
        self.captureRunnerOnThread.stopGroupImagesPool();
        self.window.destroy()
        self.isRendering = False

        
    def update(self, background,  captureRunnerOnThread):
        self.background = background
        self.captureRunnerOnThread = captureRunnerOnThread
        return self

    
    def render(self): #render(self, imageListInfo, currentIndex):
        # try:
        #     self.window.focus_set()
        # except:
        #     self.window = TK.Toplevel()
        #     pass

        # self.window.attributes('-fullscreen', True)
        # self.width = self.window.winfo_screenwidth()
        # self.height = self.window.winfo_screenheight()
        # self.window.canvas = TK.Canvas(self.window, background=self.backgroundColorToStr(), highlightthickness=0)         
        # self.window.canvas.pack(fill=TK.BOTH, expand=True) 
        # self.captureFrame = self.captureRunnerOnThread.startGroupImages().frame
        # self.parent.after(1000, self.__runCapture)
        
        self.__init__(self.parent, self.title, self.background, self.captureRunnerOnThread)
        if(self.isRendering is False):
            #self.parent.after(1000, self.__runCapture)
            t = Timer(interval=1, function=self.__runCapture)
            t.setDaemon(True);
            t.start()

        #self.window.mainloop()


    #@jit
    def __runCapture(self):
        #global yPos
        #try:
        #global imageCellSize, imageListInfo, countThreadRun, captureFram
        seconds = 0.1
        # try:
        #while len(self.captureRunnerOnThread.groupFramePool) > 0:
        #start = time()
        self.groupImageListInfo = self.captureRunnerOnThread.groupImageListInfo
        # self.captureFrame = self.captureRunnerOnThread.startGroupImages().groupFrame
        # self.window.cvImage = self.captureFrame
        # #captureImage = self.openCVImageToTkImage(self.captureFrame, (self.width, 0))
        # self.window.captureImage = self.openCVImageToTkImage(self.captureFrame, (self.width, 0))

        if(len(self.captureRunnerOnThread.groupFramePool) > 1):
            self.captureFrame = self.captureRunnerOnThread.groupFramePool[0]
            self.window.background = self.captureFrame
            self.window.canvas.itemconfig(self.window.canvasImageConfigId, image = self.window.background)
            self.captureRunnerOnThread.groupFramePool.pop(0)

        #self.window.canvas.itemconfig(self.window.canvasImageConfigId, image = self.window.captureImage)
        #self.window.canvas.update()
        #end = time()
        # seconds = end - start
        # if(seconds == 0):
        #     seconds = 0.1
        #self.window.fpsLable.config(text = int(1/seconds))
        #print (f"ON THREAD GROUP WINDOW: {self.countThreadRun} FPS: {1/seconds}" )
        self.isRendering = True
        self.countThreadRun += 1


            # if(self.countThreadRun <= 50):
            #     self.window.after(250, self.__runCapture)
            # else:
            #     self.window.after(1, self.__runCapture)
        #self.window.after(10, self.__runCapture)
        t = Timer(interval= 0.10, function=self.__runCapture)
        #t = Thread(target=self.__runCapture,daemon=True)
        t.setDaemon(True)
        t.start()

        # except:
        #     pass


        return self

    #@jit
    def resizeCVImage(self, img, size= (0,0)):
        _width, _height = img.size

        #size ->> width height
        new_width = size[0]
        new_height = size[1]

        if new_width is 0 and new_height is 0:
            return img

        dim = self.getAspectRation((_width, _height), size)

        return img.resize(dim, Image.ANTIALIAS)


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
            img = Image.fromarray(imRGB)
            img = self.resizeCVImage(img, size)
        else:
            img = WindowCapture.newBlankImageSize(self.getAspectRation((10,10, size)), self.background)
            img = Image.fromarray(img)
        return ImageTk.PhotoImage(image=img)

    #@jit(parallel=True)
    def backgroundColorToStr(self):
        return "#%02x%02x%02x" % self.background  

    def getInageCoordinates(self, x, y):
        mouseX, mouseY = x, y

        width_Unit, height_Unit = self.getAspectRation((self.captureFrame.width(),self.captureFrame.height()), (self.width, 0))
        #col, row, imageListCount, imageList
        cols,rows, count = self.groupImageListInfo
        offset_MouseY = mouseY - (self.height / 2 - height_Unit / 2)
        col_width_Unit = width_Unit / cols
        row_height_Unit = height_Unit / rows

        self.currentCol = floor(mouseX / col_width_Unit)
        self.currentRow = floor(offset_MouseY / row_height_Unit)
        self.currentIndex = (self.currentRow  * cols) + self.currentCol


    def windowClick(self, event):
        #self.showButtonFrame()
        if self.captureFrame is None: 
            return
        
        self.getInageCoordinates(event.x, event.y)
        #messagebox.showinfo(title="Coordinate", message=f"index: {self.currentIndex}, r: {self.currentRow} ,c: {self.currentCol} ")


    def windowRClick(self, event):
        #self.showButtonFrame() 
        if self.captureFrame is None: 
            return

        self.getInageCoordinates(event.x_root, event.y_root)
        # images = self.imageListInfo[3]

        if(self.currentRow >= 0  and self.currentIndex < len(self.captureRunnerOnThread.imageIndexes)): 
            self.window.menu.tk_popup(event.x_root, event.y_root)

    def menu_ClearGroupPreview(self):
        self.groupImageListInfo = self.captureRunnerOnThread.imageIndexes
        self.captureRunnerOnThread.imageIndexes.clear()
        #self.renderGroupPreviewWindow.update(self.background, self.captureRunnerOnThread)

    def menu_RemoveFromPin(self):
        self.captureRunnerOnThread.imageIndexes.pop(self.currentIndex)
        #self.renderGroupPreviewWindow.update(self.background, self.captureRunnerOnThread)
