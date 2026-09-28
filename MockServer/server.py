import glob
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()

DATASET_DIR = os.path.join(os.path.dirname(__file__), "dataset")
frame_idx = 0


@app.get("/frame.jpg")
async def get_frame():
    global frame_idx

    images = sorted(
        glob.glob(os.path.join(DATASET_DIR, "*.png"))
        + glob.glob(os.path.join(DATASET_DIR, "*.jpg"))
        + glob.glob(os.path.join(DATASET_DIR, "*.jpeg"))
    )

    if not images:
        raise HTTPException(
            status_code=404,
            detail=f"В папке {DATASET_DIR} нет картинок",
        )

    image_path = images[frame_idx % len(images)]
    frame_idx += 1

    return FileResponse(image_path)