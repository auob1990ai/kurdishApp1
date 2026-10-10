from PIL import Image, ImageEnhance, ImageFilter, ImageOps

def prepare(image, brightness=1.0, contrast=1.2, sharpness=1.5, scale=2.0, grayscale=False, denoise=True, threshold=False):
    image = image.convert('RGB')
    if grayscale:
        image = ImageOps.grayscale(image).convert('RGB')
    image = ImageEnhance.Brightness(image).enhance(max(.2,min(float(brightness),3)))
    image = ImageEnhance.Contrast(image).enhance(max(.2,min(float(contrast),3)))
    if denoise:
        image = image.filter(ImageFilter.MedianFilter(size=3))
    image = ImageEnhance.Sharpness(image).enhance(max(0,min(float(sharpness),5)))
    if float(scale) != 1:
        w,h=image.size
        image=image.resize((int(w*float(scale)),int(h*float(scale))),Image.Resampling.LANCZOS)
    if threshold:
        g=ImageOps.grayscale(image)
        g=ImageOps.autocontrast(g)
        g=g.point(lambda p: 255 if p>180 else 0)
        image=g.convert('RGB')
    return image

def crop_normalized(image, x=0, y=0, w=1, h=1):
    W,H=image.size
    x=max(0,min(1,float(x))); y=max(0,min(1,float(y)))
    w=max(.01,min(1-x,float(w))); h=max(.01,min(1-y,float(h)))
    return image.crop((int(x*W),int(y*H),int((x+w)*W),int((y+h)*H)))
