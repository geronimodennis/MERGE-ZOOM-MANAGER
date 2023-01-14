import cv2
import numpy as np
import mainGUI
from windowCaptureHandler import WindowCapture

mainGUI.window.mainloop()

def processScreenShot():
    lst = []
    # TODO: fetch window image here
    # image = cv2.imread("zoom.png")
    print("screen dimention", WindowCapture.getScreeDimention())
    imgBuff = WindowCapture("Zoom Meeting")
    screenshot = imgBuff.get_screenshot()
    print('screenshot', screenshot)

    image =  cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR) 
    image2chroma = image.copy()

    #get the 1st pixel color of the image, for chroma masking
    firstColorToMask = image[0,0]
 
    #mask exact color
    toMaskColor_lo=np.array(firstColorToMask)
    toMaskColor_hi=np.array(firstColorToMask)

    # Mask the image
    mask=cv2.inRange(image2chroma,toMaskColor_lo,toMaskColor_hi)

    # Change image to red where we found colorToMask
    image2chroma[mask>0]=(0,0,200)

    #hierarchy = 
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    for contour in contours:

        approx = cv2.approxPolyDP(contour, 0.01* cv2.arcLength(contour, True), True)
        #cv2.drawContours(image, [approx], 0, (0, 255, 0), 1)
        x = approx.ravel()[0]
        y = approx.ravel()[1] - 5

        #find square or rectangle
        if len(approx) == 4 :
            x, y , w, h = cv2.boundingRect(approx)
            aspectRatio = float(w)/h
            print(aspectRatio)
            print("H", h)
            print("W", w)
            if(h >=50 and h <= 540):
                cv2.putText(image, "rectangle", (x, y), cv2.FONT_HERSHEY_COMPLEX, 0.5, (0, 0, 0))
                cv2.rectangle(image,(x,y),(x+w,y+h),(0,255,0),5)
                print("Acceptable rec H:", h, "W", w)
                lst.append(image[y:y+h, x:x+w])

    return lst


#cv2.imshow("result.png",image)
listImage = processScreenShot()



cv2.namedWindow("window", cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty("window",cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)

#blank_image = 255*np.zeros(shape=[200, 200, 3], dtype=np.uint8)

#blank_image = 222 * np.ones(shape=[512, 512, 3], dtype=np.uint8)
#getWindowsTitle()
# cnt = 0
# for img in listImage:
#     cv2.imshow("result.png list " + str(cnt), img)
#     cv2.waitKey(20)
#     cnt +=1
# cv2.waitKey(0)
cv2.imshow("window", WindowCapture.newBlankImage())
#cv2.waitKey(0)

cv2.destroyAllWindows()

