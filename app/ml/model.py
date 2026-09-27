import logging
import os
from typing import Any
import numpy as np
from PIL import Image

logger = logging.getLogger("ml_model")

try:
    import torch
    import torchvision.models as models
    import torchvision.transforms as transforms
    from ultralytics import YOLO
    HAS_ML_LIBS = True
except ImportError:
    HAS_ML_LIBS = False
    logger.warning("ultralytics/torch не установлены. Включается режим эмулятора инференса.")


class ModelPipeline:
    def __init__(self, yolo_path: str = "best.pt"):
        self.yolo_path = yolo_path
        self.yolo_model = None
        self.reid_model = None
        self.device = "cuda" if (HAS_ML_LIBS and torch.cuda.is_available()) else "cpu"

        # Загрузка детектора YOLO (Модель 1)
        if HAS_ML_LIBS and os.path.exists(self.yolo_path):
            try:
                self.yolo_model = YOLO(self.yolo_path)
                logger.info("YOLO модель успешно загружена из '%s' (устройство: %s)", self.yolo_path, self.device)
            except Exception as e:
                logger.error("Не удалось инициализировать YOLO из %s: %s", self.yolo_path, e)
        else:
            logger.info("Файл '%s' не найден, будет использоваться резервный эмулятор детекции", self.yolo_path)

        # Легковесный экстрактор векторов ReID (Модель 2 на базе MobileNetV3)
        if HAS_ML_LIBS:
            try:
                base_model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
                base_model.classifier = torch.nn.Identity()
                base_model.eval()
                self.reid_model = base_model.to(self.device)
                
                self.transform = transforms.Compose([
                    transforms.Resize((256, 128)),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ])
                logger.info("ReID экстрактор признаков готов (MobileNetV3 -> 576-dim vector)")
            except Exception as e:
                logger.warning("Не удалось загрузить torchvision MobileNet: %s. Включаем векторный фоллбэк.", e)

    def extract_embedding(self, crop_image: Image.Image) -> list[float]:
        """Превращает вырезанную картинку машины в числовой вектор признаков"""
        if self.reid_model and HAS_ML_LIBS:
            try:
                tensor = self.transform(crop_image).unsqueeze(0).to(self.device)
                with torch.no_grad():
                    embedding = self.reid_model(tensor).squeeze(0).cpu().numpy()
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                return [round(float(v), 5) for v in embedding]
            except Exception:
                pass

        # Надежный фоллбэк без PyTorch (цвето-текстурный хэш 64 float)
        stat = np.array(crop_image.resize((8, 8))).flatten()[:64]
        norm = np.linalg.norm(stat) or 1.0
        return [round(float(v), 5) for v in (stat / norm)]

    def process_frame(self, image_path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Главный метод инференса:
        Вход: путь к файлу картинки (jpg/png)
        Выход: 
          - detection_result: список словарей с боксами и классами
          - embeddings_data: список словарей с векторами признаков
        """
        if not os.path.exists(image_path):
            logger.warning("Кадр не найден по пути: %s", image_path)
            return [], []

        try:
            image = Image.open(image_path).convert("RGB")
        except Exception as e:
            logger.error("Ошибка чтения изображения %s: %s", image_path, e)
            return [], []

        detections = []
        embeddings = []

        # Реальный запуск твоей YOLO-модели
        if self.yolo_model:
            results = self.yolo_model(image_path, conf=0.30, verbose=False)[0]

            for idx, box in enumerate(results.boxes):
                cls_id = int(box.cls[0].item())
                # Приводим класс к нижнему регистру (excavator, dump_truck и т.д.)
                cls_name = results.names.get(cls_id, f"class_{cls_id}").lower()
                conf = float(box.conf[0].item())
                xyxy = [int(v) for v in box.xyxy[0].tolist()]

                # Вырезаем фрагмент техники по координатам бокса
                crop = image.crop((xyxy[0], xyxy[1], xyxy[2], xyxy[3]))
                vector = self.extract_embedding(crop)

                detections.append({
                    "idx": idx,
                    "class": cls_name,
                    "confidence": round(conf, 2),
                    "bbox": xyxy,
                })
                embeddings.append({
                    "idx": idx,
                    "vector": vector,
                })

            return detections, embeddings

        # Резервный режим (если best.pt ещё не положили, чтобы ничего не падало)
        w, h = image.size
        mock_objects = [
            ("excavator", 0.92, [int(w * 0.15), int(h * 0.25), int(w * 0.45), int(h * 0.65)]),
            ("dump_truck", 0.89, [int(w * 0.55), int(h * 0.30), int(w * 0.85), int(h * 0.70)]),
        ]

        for idx, (cls_name, conf, bbox) in enumerate(mock_objects):
            crop = image.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
            vector = self.extract_embedding(crop)
            detections.append({
                "idx": idx,
                "class": cls_name,
                "confidence": conf,
                "bbox": bbox,
            })
            embeddings.append({
                "idx": idx,
                "vector": vector,
            })

        return detections, embeddings


def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Вычисляет косинусное сходство (от 0.0 до 1.0) между двумя векторами машин"""
    a = np.array(vec_a)
    b = np.array(vec_b)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))