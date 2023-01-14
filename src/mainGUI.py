from numba import jit
from time import *
import tkinter as TK
from tkinter.colorchooser import askcolor
from tkinter import messagebox

from math import *
from WindowRenderer import WindowRenderer
#from WindowRenderer import WindowRenderer
from captureRunnerOnThread import CaptureRunnerOnThread
from win32Manager import getWindowsTitle
from PIL import Image, ImageTk
from win32api import GetSystemMetrics

import threading

import cv2

from windowCaptureHandler import WindowCapture

_captureConfiguration = [{
    "winName": "",
    "win_hwnd": any,
    "index": 0, 
    "optionMenu": any,
    "optionMenuStringVar": any,
    "optionMenuCallback": any,
    "previewCanvas": any,
    "captureHandler": None,
}]

_chromaColorKey = (0,177,64)

window = TK.Tk()
window.title("MCGI ADDPRO-TOOL : COMBINE ZOOM GALLERIE : Setup Capture : (By DenG - NCR/QMD)")
renderWindow = None #WindowRenderer(_chromaColorKey,_captureConfiguration)


options = [""]
firstLoad = True
imageValue = None

captureFrame = None
countThreadRun = 0
imageCellSize = (0,0)
imageListInfo = None

def rgb_hack(rgb):
    return "#%02x%02x%02x" % rgb  

def _updateOptionList():
    global options, firstLoad
    txt = _txtWindowNameSearch
    options = getWindowsTitle()
    findWhat = txt.get()
    newOptionValue = [""]
    print ("after event")
    if(findWhat != ""):
        for str in options:
            if findWhat.lower() in str.lower():
                newOptionValue.append(str)
        options = newOptionValue

    newOptionValue = options

    if(firstLoad):
        firstLoad = False
        return


    if(options not in newOptionValue):
        for cfg in _captureConfiguration:  
            print(cfg["optionMenu"])
   
            cfg["optionMenu"]["menu"].delete(0, 'end')
            for opt in options:
                optionMenuStringVar = cfg["optionMenuStringVar"]
                cfg["optionMenu"]["menu"].add_command(label=opt,command = TK._setit(optionMenuStringVar, opt, cfg["optionMenuCallback"]))

            #cfg["optionMenu"].set_menu(*options)



def _createSeach():
    global _txtWindowNameSearch
    _frameForSearch = TK.Frame(window, width=100)

    _lblWindowNameSearch = TK.Label(_frameForSearch, text = "Window Search")
    _txtWindowNameSearch = TK.Entry(_frameForSearch)
    _txtWindowNameSearch.insert(TK.INSERT, "zoom meeting")

    _lblWindowNameSearch.grid(row=0,column=0)
    _txtWindowNameSearch.grid(row=0,column=1, columnspan=3)

    _frameForSearch.grid() 
 
    #_updateOptionList()

#
# def runCaptureClick():
#     global renderWindow
#     if(renderWindow is None):
#         renderWindow = WindowRenderer(_chromaColorKey,_captureConfiguration)
#     renderWindow.show()
#     renderWindow.render()

def runCaptureClickV2():
    global renderWindow
    if(renderWindow is None):
        renderWindow = WindowRenderer(_chromaColorKey, _captureConfiguration)

    renderWindow.background = _chromaColorKey
    renderWindow.render()



def runCaptureClick():
    global renderWindow, countThreadRun, captureFrame
    try:
        renderWindow.focus_set()
        return
    except Exception:
        renderWindow = TK.Toplevel() #TK.Tk()
        renderWindow.title("MCGI ADDPRO-TOOL : COMBINE ZOOM GALLERIES")
        renderWindow.attributes('-fullscreen', True)
        pass
        

    screen_width = renderWindow.winfo_screenwidth()
    screen_height = renderWindow.winfo_screenheight()

    renderWindow.canvas = TK.Canvas(renderWindow, background=rgb_hack(_chromaColorKey), highlightthickness=0)      
    renderWindow.canvas.pack(fill=TK.BOTH, expand=True)  

    def motion(event):
        if captureFrame is None: 
            return

        mouseX, mouseY = event.x, event.y

        width_Unit, height_Unit = getAspectRation((captureFrame.shape[1],captureFrame.shape[0]), (screen_width, 0))
        #col, row, imageListCount, imageList
        cols,rows, count, images = imageListInfo
        offset_MouseY = mouseY - (screen_height / 2 - height_Unit / 2)
        col_width_Unit = width_Unit / cols
        row_height_Unit = height_Unit / rows



        currentCol = floor(mouseX / col_width_Unit)
        currentRow = floor(offset_MouseY / row_height_Unit)
        if(currentRow is 0):
            currentIndex = currentCol
        else:
            currentIndex = ((currentRow * rows) + currentCol) + 1

        cv2.imshow("preview", images[ currentIndex ])
        #messagebox.showinfo(title="Sample", message='currentCol {}, {}'.format(currentCol, currentRow))

    
    renderWindow.bind('<Button-1>', motion)


    
    captureRunnerOnThread = CaptureRunnerOnThread(_captureConfiguration, _chromaColorKey).startNoThread()

    countThreadRun = 0
    def __runCapture():
        global imageCellSize, imageListInfo, countThreadRun, captureFrame
        start = time.time()
        # try:
        #img = captureRunnerOnThread.startNoThread().frame
        
        captureFrame = captureRunnerOnThread.start().frame
        imageCellSize = captureRunnerOnThread.uniformSize
        imageListInfo = captureRunnerOnThread.imageListInfo

        #img = np.ascontiguousarray(img)

        renderWindow.cvImage = captureFrame
        captureImage = openCVImageToTkImage(captureFrame, (screen_width, 0))
        renderWindow.background = captureImage

        _yPos = screen_height/2 - captureImage.height()/2
        if(_yPos < 0): 
            yPos = 0

        renderWindow.canvas.create_image(0, _yPos, image=captureImage, anchor=TK.NW)
        #renderWindow.canvas.update()
        countThreadRun +=1

        end = time.time()
        seconds = end - start



        print ("ON THREAD_______________", countThreadRun , f"FPS: {1/seconds}" )
        countThreadRun +=1
        # except:
        #     pass

        renderWindow.after(10, __runCapture)


    renderWindow.after(10, __runCapture)
    #renderWindow.mainloop()
    
 
def resizeCVImage(img, size= (0,0)):
    _width, _height = img.size

    #size ->> width height
    new_width = size[0]
    new_height = size[1]

    if new_width is 0 and new_height is 0:
        return img

    dim = getAspectRation((_width, _height), size)

    return img.resize(dim, Image.ANTIALIAS)

#size1 (w,h), size2 (w,h)
def getAspectRation(size1,size2= (0,0)):
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



def openCVImageToTkImage(cvImage, size = (0,100)):
   
    if not cvImage is None: 
        imRGB = cvImage[:, :, ::-1]
        img = Image.fromarray(imRGB)
        img = resizeCVImage(img, size)
    else:
        img = WindowCapture.newBlankImageSize(getAspectRation((10,10, size)), _chromaColorKey)
        img = Image.fromarray(img)
    return ImageTk.PhotoImage(image=img)



def selectChroma(buttonChroma):
    global _chromaColorKey
    colors  = askcolor(title ="Choose color", color=_chromaColorKey)
    _chromaColorKey = colors[0]
    if(_chromaColorKey): 
        buttonChroma.config(background=rgb_hack(_chromaColorKey))
        buttonChroma.update()


def _createDataGrid():
    _frameForDataGrid = TK.Frame(window)
    _frameDataGridHeader = TK.Frame(_frameForDataGrid)
    _frameDataGridHeader.config(background=rgb_hack(_chromaColorKey))
    TK.Button(_frameDataGridHeader, text='ADD', width=10,command=lambda: _addRow(_frameForDataGrid, True)).grid(row=0,column=1)
    
    buttonChroma = TK.Button(_frameDataGridHeader, text='CHROMA', width=10,command=lambda: selectChroma(_frameDataGridHeader)).grid(row=0,column=2)
 
    #TK.Button(_frameDataGridHeader, text='RUN', width=10,command=lambda: runCaptureClickV2()).grid(row=0,column=4)
    TK.Button(_frameDataGridHeader, text='RENDER', width=10,command=lambda: runCaptureClickV2()).grid(row=0,column=3)
    TK.Label(_frameDataGridHeader, bg="GRAY", text="DEL", relief=TK.FLAT, width=10).grid(row=1,column=1)
    TK.Label(_frameDataGridHeader, bg="GRAY", text="SELECT WINDOW", relief=TK.FLAT, width=80).grid(row=1,column=2)
    TK.Label(_frameDataGridHeader, bg="GRAY", text="PREVIEW", relief=TK.FLAT, width=40).grid(row=1,column=3)
    _frameDataGridHeader.grid()
    _frameForDataGrid.grid()
    
    def _createDataGridRows(_dataGridFrame):
        _rowIndex = 0
        for cfg in _captureConfiguration:
            _addRow(_dataGridFrame, _rowIndex != 0)
            _rowIndex+=1


    def _addRow(frameForDataGrid, isShowDelete):
        _frameDataGridRows = TK.Frame(frameForDataGrid.master.master)

        def _windowNameSelectChange(choice):
            print("asd", _frameDataGridRows.grid_info(), choice)
            hwnd = choice.split(":",1)[0]
            #hwnd = int(hwnd)
            r = _frameDataGridRows.grid_info()["row"] - 2
            config = _captureConfiguration[r]
            config["winName"] = choice
            captureHandler = config["captureHandler"]
            if(not captureHandler):
                print("create new WindowCapture window_name=hwnd")
                config["captureHandler"] = captureHandler = WindowCapture(hwnd=hwnd)
            else:
                print("reuse WindowCapture")
                captureHandler.resetCapture(hwnd=hwnd)

            canvas = config["previewCanvas"];
            canvas.cvImage = captureHandler.get_screenshot()
            captureImage = openCVImageToTkImage(canvas.cvImage)
            canvas.background = captureImage
    
            #canvas.image = captureImage
            canvas.create_image(0, 0, image=captureImage, anchor=TK.NW)
            #canvas.update() 
            #cv2.imshow("windoiw", captureHandler.get_screenshot())


        def _deleteRow(frameDataGridRows):    
            print("_captureConfiguration before") 

            for cfg in _captureConfiguration:
                print("before:", cfg["winName"])

            _r = _frameDataGridRows.grid_info()["row"] - 2
            frameDataGridRows.grid_forget()
            frameDataGridRows.destroy()
            try:
                if(_r > len(_captureConfiguration)):
                    _r =  len(_captureConfiguration)-1
                _captureConfiguration.pop(_r)
            except:
                _captureConfiguration.pop(_r-1)
            
            del frameDataGridRows
        


        _updateOptionList()
        optionMenuStringVar = TK.StringVar()
        dropdown = TK.OptionMenu(_frameDataGridRows, optionMenuStringVar, *options, command=_windowNameSelectChange );
        dropdown.config(width=80)
        dropdown.grid(row=0,column=2, sticky=TK.W)


        if(isShowDelete == False):
            _captureConfiguration[0]["optionMenu"] = dropdown
            _captureConfiguration[0]["optionMenuStringVar"] = optionMenuStringVar
            _captureConfiguration[0]["optionMenuCallback"]  = _windowNameSelectChange
            #_captureConfiguration[0]["previewCanvas"] = TK.Label(_frameDataGridRows, text="PREVIEW", relief=TK.RIDGE, width=40)
            _captureConfiguration[0]["previewCanvas"] = previewCanvas = TK.Canvas(_frameDataGridRows,width=200, height=100) #bg='black'
            _captureConfiguration[0]["previewCanvas"].grid(row=0,column=4)

            TK.Label(_frameDataGridRows, text=" ", width=10).grid(row=0,column=1)
        else:
            TK.Button(_frameDataGridRows, text="DEL", width=10,command=lambda: _deleteRow(_frameDataGridRows)).grid(row=0,column=1)
            __config = {
                "winName": "zoom",
                "index": 0,
                "optionMenu": dropdown,
                "optionMenuStringVar": optionMenuStringVar,
                "optionMenuCallback": _windowNameSelectChange,
                #"previewCanvas": TK.Label(_frameDataGridRows, text="PREVIEW", relief=TK.RIDGE, width=40),
                "previewCanvas": TK.Canvas(_frameDataGridRows, width=200, height=100), #bg='black'
                "captureHandler": None
            }

            previewCanvas = __config["previewCanvas"]
            __config["previewCanvas"].grid(row=0,column=4)
            _captureConfiguration.append(__config)
   
        def callback(event):
            r = event.widget.master.grid_info()["row"] - 2
            config = _captureConfiguration[r]
            _h,_w,_ = event.widget.cvImage.shape;
            captureHandler = config["captureHandler"]
            event.widget.cvImage = captureHandler.get_screenshot()
            captureImage = openCVImageToTkImage(event.widget.cvImage)
            event.widget.background = captureImage

            print("event widget",event.widget, '_h', _h, '_w', _w)
            event.widget.create_image(0, 0, image=captureImage, anchor=TK.NW)
            dim = (int(_w * 0.5), int(_h * 0.5))
            resized = cv2.resize(event.widget.cvImage, dim, interpolation = cv2.INTER_AREA)
            cv2.imshow("preview", resized)

        previewCanvas.bind("<Button-1>", callback)
        TK.Button(_frameDataGridRows, text="Refresh list", width=10, command=_updateOptionList).grid(row=0,column=3)
        #TK.Label(_frameDataGridRows, text="PREVIEW", relief=TK.RIDGE, width=40).grid(row=0,column=4)
        #TK.Canvas(_frameDataGridRows,  width = 300, height = 300).grid(row=0,column=4)
        _frameDataGridRows.grid()
    
    _createDataGridRows(_frameForDataGrid)

_createSeach()
_createDataGrid()


def on_closing():
    if messagebox.askokcancel("Quit", "Do you want to quit?"):
        window.destroy()
        quit()
        cv2.destroyAllWindows()
        


if __name__ == '__main__':
    window.protocol("WM_DELETE_WINDOW", on_closing)
    window.mainloop()
