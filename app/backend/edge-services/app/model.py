import numpy as np
import onnxruntime as ort
from PIL import Image
from app.config import settings

class YoloOnnx:
    def __init__(self):
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        try:
            self.session = ort.InferenceSession(settings.yolo_model_path, providers=providers)
            self.input_name = self.session.get_inputs()[0].name
        except Exception:
            self.session = None
            self.input_name = None
        self.input_size = settings.yolo_input_size
        self.conf = settings.yolo_conf_threshold
        self.iou = settings.yolo_iou_threshold
        self.labels = [l.strip() for l in settings.yolo_labels.split(",") if l.strip()]

    def preprocess(self, image_bytes):
        img = Image.open(io_bytes(image_bytes)).convert("RGB")
        w, h = img.size
        r = min(self.input_size / w, self.input_size / h)
        nw, nh = int(w * r), int(h * r)
        resized = img.resize((nw, nh))
        canvas = Image.new("RGB", (self.input_size, self.input_size), (114, 114, 114))
        pad_w = (self.input_size - nw) // 2
        pad_h = (self.input_size - nh) // 2
        canvas.paste(resized, (pad_w, pad_h))
        arr = np.array(canvas).astype(np.float32) / 255.0
        arr = np.transpose(arr, (2, 0, 1))[None, ...]
        return arr, (r, pad_w, pad_h), (w, h)

    def postprocess(self, preds, scale_pad, orig_size):
        r, pad_w, pad_h = scale_pad
        w, h = orig_size
        preds = preds[0]
        boxes = preds[:, :4]
        obj = preds[:, 4:5]
        cls = preds[:, 5:]
        cls_id = np.argmax(cls, axis=1)
        cls_score = cls[np.arange(len(cls)), cls_id]
        scores = (obj.squeeze(1) * cls_score).astype(np.float32)
        keep = scores >= self.conf
        boxes = boxes[keep]
        scores = scores[keep]
        cls_id = cls_id[keep]
        if boxes.size == 0:
            return []

        x, y, bw, bh = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        x1 = x - bw / 2
        y1 = y - bh / 2
        x2 = x + bw / 2
        y2 = y + bh / 2

        x1 = (x1 - pad_w) / r
        y1 = (y1 - pad_h) / r
        x2 = (x2 - pad_w) / r
        y2 = (y2 - pad_h) / r

        x1 = np.clip(x1, 0, w)
        y1 = np.clip(y1, 0, h)
        x2 = np.clip(x2, 0, w)
        y2 = np.clip(y2, 0, h)

        dets = np.stack([x1, y1, x2, y2, scores, cls_id], axis=1)
        dets = nms(dets, self.iou)
        out = []
        for d in dets:
            label = self.labels[int(d[5])] if int(d[5]) < len(self.labels) else "parcel"
            out.append({
                "x1": float(d[0]),
                "y1": float(d[1]),
                "x2": float(d[2]),
                "y2": float(d[3]),
                "score": float(d[4]),
                "label": label
            })
        return out

    def infer(self, image_bytes):
        if not self.session:
            return []
        inp, scale_pad, orig_size = self.preprocess(image_bytes)
        preds = self.session.run(None, {self.input_name: inp})[0]
        return self.postprocess(preds, scale_pad, orig_size)

class EmbedOnnx:
    def __init__(self):
        if not settings.embed_model_path:
            self.session = None
            return
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.session = ort.InferenceSession(settings.embed_model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = settings.embed_input_size
        self.dim = settings.embed_dim

    def preprocess(self, image_bytes, box):
        img = Image.open(io_bytes(image_bytes)).convert("RGB")
        crop = img.crop((box["x1"], box["y1"], box["x2"], box["y2"]))
        crop = crop.resize((self.input_size, self.input_size))
        arr = np.array(crop).astype(np.float32) / 255.0
        arr = np.transpose(arr, (2, 0, 1))[None, ...]
        return arr

    def embed(self, image_bytes, box):
        if not self.session:
            return np.zeros(settings.embed_dim, dtype=np.float32).tolist()
        inp = self.preprocess(image_bytes, box)
        out = self.session.run(None, {self.input_name: inp})[0]
        vec = out.reshape(-1).astype(np.float32)
        if vec.shape[0] != settings.embed_dim:
            vec = vec[:settings.embed_dim]
        return vec.tolist()

def io_bytes(b):
    from io import BytesIO
    return BytesIO(b)

def nms(dets, iou_thres):
    if dets.size == 0:
        return dets
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        area1 = (x2[i] - x1[i]) * (y2[i] - y1[i])
        area2 = (x2[order[1:]] - x1[order[1:]]) * (y2[order[1:]] - y1[order[1:]])
        iou = inter / (area1 + area2 - inter + 1e-6)
        inds = np.where(iou <= iou_thres)[0]
        order = order[inds + 1]
    return dets[keep]

_yolo = YoloOnnx()
_embed = EmbedOnnx()

def run_inference(image_bytes):
    detections = _yolo.infer(image_bytes)
    if detections:
        fingerprint = _embed.embed(image_bytes, detections[0])
    else:
        fingerprint = np.zeros(settings.embed_dim, dtype=np.float32).tolist()
    return detections, fingerprint, None
