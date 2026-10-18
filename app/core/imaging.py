import base64
import io
import os
from PIL import Image, ImageDraw, ImageFont


def image_file_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"


def render_annotated_frame(
    image_path: str,
    detections: list[dict],
    class_name_map: dict[str, str],
) -> tuple[str, list[str]]:
    """
    Накладывает рамки и русские подписи из БД.
    Возвращает (annotated_base64, список_уникальных_русских_названий).
    """
    if not os.path.exists(image_path):
        return "", []

    with Image.open(image_path) as img:
        annotated = img.convert("RGB")
        draw = ImageDraw.Draw(annotated)

        try:
            font = ImageFont.load_default(size=18)
        except TypeError:
            font = ImageFont.load_default()

        detected_labels = []

        for d in detections:
            bbox = d.get("bbox", [])
            if len(bbox) != 4:
                continue

            x1, y1, x2, y2 = [int(v) for v in bbox]
            raw_cls = d.get("class", "").lower()

            label_ru = class_name_map.get(raw_cls, raw_cls.capitalize())
            detected_labels.append(label_ru)

            draw.rectangle([x1, y1, x2, y2], outline="#16a34a", width=3)

            text_bbox = draw.textbbox((x1, y1), label_ru, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            box_top = max(0, y1 - text_h - 6)

            draw.rectangle([x1, box_top, x1 + text_w + 10, y1], fill="#16a34a")
            draw.text((x1 + 5, box_top + 2), label_ru, fill="#ffffff", font=font)

        buffer = io.BytesIO()
        annotated.save(buffer, format="JPEG", quality=85)
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        
        return f"data:image/jpeg;base64,{encoded}", list(set(detected_labels))