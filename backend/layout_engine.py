from PIL import Image
import numpy as np

def detect_text_regions(image, min_area=0.003, max_regions=30):
    """Detect coarse text blocks using OpenCV morphology. Returns normalized x,y,w,h sorted top-to-bottom/right-to-left for RTL pages."""
    try:
        import cv2
    except ImportError:
        return []
    arr=np.array(image.convert('L'))
    h,w=arr.shape
    bw=cv2.threshold(arr,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(max(15,w//40),max(3,h//180)))
    merged=cv2.morphologyEx(bw,cv2.MORPH_CLOSE,kernel,iterations=1)
    contours,_=cv2.findContours(merged,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    boxes=[]
    for c in contours:
        x,y,ww,hh=cv2.boundingRect(c); area=ww*hh
        if area < w*h*min_area: continue
        if ww < w*.08 or hh < h*.008: continue
        if ww > w*.98 and hh > h*.98: continue
        boxes.append((x,y,ww,hh))
    boxes=sorted(boxes,key=lambda b:(b[1],-b[0]))[:max_regions]
    boxes=sorted(boxes,key=lambda b:(b[1]//max(1,h//40),-b[0]))
    return [{"x":round(x/w,5),"y":round(y/h,5),"w":round(ww/w,5),"h":round(hh/h,5)} for x,y,ww,hh in boxes]
