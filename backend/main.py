from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pydantic import BaseModel
from typing import Optional
try:
    # Production package import (Docker/Render)
    from .kurdish_corrector import correct_sorani, normalize_sorani
    from .ocr_engine import prepare, crop_normalized
    from .layout_engine import detect_text_regions
except ImportError:
    # Local development: run `uvicorn main:app` from the backend directory
    from kurdish_corrector import correct_sorani, normalize_sorani
    from ocr_engine import prepare, crop_normalized
    from layout_engine import detect_text_regions
from io import BytesIO
import os, uuid, re, tempfile, statistics
_WHISPER_CACHE = {}

app = FastAPI(title="KurdText API", version="0.6.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/files", StaticFiles(directory=UPLOAD_DIR), name="files")

LANGS = {"ckb": "Kurdish Sorani", "fa": "Persian", "ar": "Arabic", "en": "English"}

# Conservative normalization: it fixes common Unicode variants without rewriting valid words.
def normalize_text(text: str, language: str) -> str:
    if language == "ckb":
        text = normalize_sorani(text)
    else:
        text = text.replace("\u064a", "\u06cc").replace("\u0649", "\u06cc")
        text = text.replace("\u0643", "\u06a9").replace("\u0640", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text

@app.post("/api/correct")
async def correct_text(file: Optional[UploadFile] = None, text: str = Form(""), language: str = Form("ckb")):
    if language not in LANGS:
        raise HTTPException(400, "زبان پشتیبانی نمی‌شود")
    if file is not None and not text:
        text = (await file.read()).decode("utf-8", errors="ignore")
    text = normalize_text(text, language)
    if language == "ckb":
        corrected, corrections = correct_sorani(text)
    else:
        corrected, corrections = text, []
    return {"text": corrected, "corrections": corrections, "language": language, "status": "ok"}

@app.get("/api/health")
def health():
    return {"ok": True, "service": "KurdText", "languages": list(LANGS)}

@app.post("/api/image/preprocess")
async def preprocess_image(file: UploadFile = File(...), brightness: float = Form(1.0), contrast: float = Form(1.2), sharpness: float = Form(1.5), scale: float = Form(2.0), grayscale: bool = Form(False)):
    raw = await file.read()
    try: img = Image.open(BytesIO(raw)).convert("RGB")
    except Exception: raise HTTPException(400, "فایل تصویر معتبر نیست")
    if grayscale: img = ImageOps.grayscale(img).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(max(.2, min(float(brightness), 3)))
    img = ImageEnhance.Contrast(img).enhance(max(.2, min(float(contrast), 3)))
    img = ImageEnhance.Sharpness(img).enhance(max(0, min(float(sharpness), 5)))
    if float(scale) != 1:
        w,h=img.size; img=img.resize((int(w*float(scale)),int(h*float(scale))), Image.Resampling.LANCZOS)
    name=f"{uuid.uuid4().hex}.png"; path=os.path.join(UPLOAD_DIR,name); img.save(path,"PNG",optimize=True)
    return {"filename":name,"width":img.width,"height":img.height,"url":f"/files/{name}"}

def _tesseract(image, language, psm=6):
    import pytesseract
    tess_lang={"ckb":"ckb","fa":"fas","ar":"ara","en":"eng"}[language]
    data=pytesseract.image_to_data(image, lang=tess_lang, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    words=[]; confs=[]
    for i,raw in enumerate(data.get("text", [])):
        word=(raw or "").strip()
        try: conf=float(data["conf"][i])
        except Exception: conf=-1
        if word:
            words.append(word)
            if conf >= 0: confs.append(conf)
    text=" ".join(words)
    avg=round(statistics.mean(confs),1) if confs else 0
    return normalize_text(text,language), avg

@app.post("/api/ocr")
async def ocr(file: UploadFile = File(...), language: str = Form("ckb"), brightness: float = Form(1.0), contrast: float = Form(1.2), sharpness: float = Form(1.5), scale: float = Form(2.0), grayscale: bool = Form(False), crop_x: float = Form(0), crop_y: float = Form(0), crop_w: float = Form(1), crop_h: float = Form(1), threshold: bool = Form(False)):
    if language not in LANGS: raise HTTPException(400, "زبان پشتیبانی نمی‌شود")
    raw=await file.read()
    try: image=Image.open(BytesIO(raw)).convert("RGB")
    except Exception: raise HTTPException(400,"فایل تصویر معتبر نیست")
    image=crop_normalized(image,crop_x,crop_y,crop_w,crop_h)
    try:
        image=prepare(image,brightness,contrast,sharpness,scale,grayscale,True,threshold)
        text,confidence=_tesseract(image,language,6)
        return {"text":text,"language":language,"status":"ok","engine":"tesseract","confidence":confidence}
    except Exception as exc:
        return {"text":"","language":language,"status":"engine_not_ready","engine":"tesseract","message":"موتور OCR محلی یا فایل زبان آن روی سرور نصب نشده است.","detail":str(exc)}

@app.post("/api/ocr/auto")
async def ocr_auto(file: UploadFile = File(...), language: str = Form("ckb"), brightness: float = Form(1.0), contrast: float = Form(1.2), sharpness: float = Form(1.5), scale: float = Form(2.0), grayscale: bool = Form(False), threshold: bool = Form(False)):
    if language not in LANGS: raise HTTPException(400, "زبان پشتیبانی نمی‌شود")
    raw=await file.read()
    try: image=Image.open(BytesIO(raw)).convert("RGB")
    except Exception: raise HTTPException(400,"فایل تصویر معتبر نیست")
    try:
        regions=detect_text_regions(image)
        base=prepare(image,brightness,contrast,sharpness,scale,grayscale,True,threshold)
        if not regions:
            text,conf=_tesseract(base,language,3)
            return {"text":text,"language":language,"status":"ok","engine":"tesseract-auto","regions":0,"confidence":conf}
        results=[]
        for r in regions:
            crop=crop_normalized(base,r["x"],r["y"],r["w"],r["h"])
            txt,conf=_tesseract(crop,language,6)
            if txt.strip(): results.append((r,txt,conf))
        results.sort(key=lambda item:(item[0]["y"],-item[0]["x"]))
        merged="\n".join(x[1] for x in results)
        conf=round(statistics.mean([x[2] for x in results]),1) if results else 0
        return {"text":normalize_text(merged,language),"language":language,"status":"ok","engine":"tesseract-auto","regions":len(results),"confidence":conf}
    except Exception as exc:
        return {"text":"","language":language,"status":"engine_not_ready","engine":"tesseract-auto","message":"پردازش خودکار OCR آماده نیست.","detail":str(exc)}

@app.post("/api/layout")
async def layout(file: UploadFile = File(...)):
    raw=await file.read()
    try: image=Image.open(BytesIO(raw)).convert("RGB")
    except Exception: raise HTTPException(400,"فایل تصویر معتبر نیست")
    regions=detect_text_regions(image)
    return {"regions":regions,"count":len(regions),"status":"ok"}

@app.post("/api/speech")
async def speech(file: UploadFile = File(...), language: str = Form("ckb")):
    if language not in LANGS: raise HTTPException(400,"زبان پشتیبانی نمی‌شود")
    suffix=os.path.splitext(file.filename or "audio")[1] or ".wav"
    fd,path=tempfile.mkstemp(suffix=suffix); os.close(fd)
    try:
        with open(path,"wb") as f: f.write(await file.read())
        # Optional local faster-whisper adapter. No external API is required.
        try:
            from faster_whisper import WhisperModel
            model_name=os.getenv("WHISPER_MODEL","small")
            cache_key=(model_name,os.getenv("WHISPER_DEVICE","cpu"),os.getenv("WHISPER_COMPUTE","int8"))
            model=_WHISPER_CACHE.get(cache_key)
            if model is None:
                model=WhisperModel(model_name, device=cache_key[1], compute_type=cache_key[2])
                _WHISPER_CACHE[cache_key]=model
            segments,info=model.transcribe(path, language=None if language=="ckb" else {"fa":"fa","ar":"ar","en":"en"}[language], vad_filter=True)
            text=" ".join(s.text.strip() for s in segments)
            return {"text":normalize_text(text,language),"language":language,"status":"ok","engine":"faster-whisper"}
        except Exception as exc:
            return {"text":"","language":language,"status":"engine_not_ready","engine":"faster-whisper","message":"مدل گفتار محلی نصب/دانلود نشده است.","detail":str(exc)}
    finally:
        try: os.remove(path)
        except OSError: pass


# In production the built React app is served by the same FastAPI service.
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
