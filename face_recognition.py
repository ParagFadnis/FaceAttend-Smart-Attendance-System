import os, re, zipfile, pickle
from datetime import datetime
import cv2
import numpy as np
import pandas as pd
from deepface import DeepFace

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ZIP_FILE = os.path.join(BASE_DIR, "ABCD.zip")
EXTRACT_DIR = os.path.join(BASE_DIR, "student_photos")
ATTENDANCE_CSV = os.path.join(BASE_DIR, "attendance.csv")
EMBED_CACHE = os.path.join(BASE_DIR, "embeddings.pkl")
MODEL_NAME = "Facenet512"
DETECTOR = "retinaface"
THRESHOLD = 0.40
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

os.makedirs(EXTRACT_DIR, exist_ok=True)

def extract_dataset():
    if not os.path.exists(ZIP_FILE):
        raise FileNotFoundError(f"ABCD.zip not found: {ZIP_FILE}")
    with zipfile.ZipFile(ZIP_FILE, "r") as z:
        z.extractall(EXTRACT_DIR)
    return [
        os.path.join(root, f)
        for root, _, fs in os.walk(EXTRACT_DIR)
        for f in fs
        if os.path.splitext(f)[1].lower() in IMAGE_EXTENSIONS
    ]

def extract_name(filepath):
    name = os.path.splitext(os.path.basename(filepath))[0]
    name = name.split(" - ")[-1].strip()
    return re.sub(r"^(MS|MR|DR)\.?\s*", "", name, flags=re.I).strip().title()

def build_student_registry(files):
    registry = {}
    for path in files:
        name = extract_name(path)
        if name and name not in registry:
            registry[name] = path
    return registry

def build_embedding_database(registry):
    if os.path.exists(EMBED_CACHE):
        with open(EMBED_CACHE, "rb") as f:
            data = pickle.load(f)
        if data:
            return data

    embeddings = {}
    for name, path in registry.items():
        try:
            result = DeepFace.represent(
                img_path=path, model_name=MODEL_NAME,
                detector_backend=DETECTOR,
                enforce_detection=False, align=True
            )
            if result:
                embeddings[name] = np.array(result[0]["embedding"])
        except Exception as e:
            print(f"Embedding failed for {name}: {e}")

    if not embeddings:
        raise RuntimeError("No embeddings created. Check ABCD.zip and student photos.")

    with open(EMBED_CACHE, "wb") as f:
        pickle.dump(embeddings, f)
    return embeddings

def load_model_data():
    registry = build_student_registry(extract_dataset())
    if not registry:
        raise RuntimeError("No student photos found.")
    return registry, build_embedding_database(registry)

def cosine_distance(a, b):
    a, b = np.asarray(a), np.asarray(b)
    den = np.linalg.norm(a) * np.linalg.norm(b)
    return 1.0 if den == 0 else float(1 - np.dot(a, b) / den)

def recognize_face(image, embeddings_db):
    if not embeddings_db:
        return []
    try:
        detected = DeepFace.represent(
            image, model_name=MODEL_NAME,
            detector_backend=DETECTOR,
            enforce_detection=False, align=True
        )
    except Exception as e:
        print("Recognition error:", e)
        return []

    results = []
    for face in detected:
        emb = np.array(face["embedding"])
        region = face.get("facial_area", {})
        distances = {n: cosine_distance(emb, db) for n, db in embeddings_db.items()}
        matches = sorted(distances.items(), key=lambda x: x[1])
        if not matches:
            continue
        best_name, dist = matches[0]
        confidence = round(max(0, min(100, (1 - dist) * 100)), 1)
        identity = best_name if dist <= THRESHOLD else "Unknown"
        results.append({
            "name": identity,
            "distance": round(dist, 4),
            "confidence": confidence,
            "bbox": region
        })
    return results

def init_attendance_csv(names):
    today = datetime.now().strftime("%Y-%m-%d")
    df = pd.DataFrame({
        "Student Name": sorted(names),
        "Status": "Absent",
        "Time": "",
        "Date": today,
        "Confidence %": ""
    })
    df.to_csv(ATTENDANCE_CSV, index=False)
    return df

def ensure_attendance_csv(names):
    if not os.path.exists(ATTENDANCE_CSV):
        return init_attendance_csv(names)
    return pd.read_csv(ATTENDANCE_CSV)

def mark_attendance(name, confidence):
    if name == "Unknown" or not os.path.exists(ATTENDANCE_CSV):
        return False
    df = pd.read_csv(ATTENDANCE_CSV, dtype={"Time": object, "Confidence %": object})
    df["Time"] = df["Time"].where(df["Time"].notna(), "")
    df["Confidence %"] = df["Confidence %"].where(df["Confidence %"].notna(), "")
    mask = df["Student Name"].astype(str).str.lower() == name.lower()
    if not mask.any() or str(df.loc[mask, "Status"].values[0]) == "Present":
        return False
    df.loc[mask, "Status"] = "Present"
    df.loc[mask, "Time"] = datetime.now().strftime("%H:%M:%S")
    df.loc[mask, "Confidence %"] = confidence
    df.to_csv(ATTENDANCE_CSV, index=False)
    return True

def manual_mark_attendance(name, status):
    if not os.path.exists(ATTENDANCE_CSV) or status not in {"Present", "Absent"}:
        return False
    df = pd.read_csv(ATTENDANCE_CSV, dtype={"Time": object, "Confidence %": object})
    df["Time"] = df["Time"].where(df["Time"].notna(), "")
    df["Confidence %"] = df["Confidence %"].where(df["Confidence %"].notna(), "")
    mask = df["Student Name"].astype(str).str.lower() == name.lower()
    if not mask.any():
        return False
    df.loc[mask, "Status"] = status
    df.loc[mask, "Time"] = datetime.now().strftime("%H:%M:%S") if status == "Present" else ""
    df.loc[mask, "Confidence %"] = "Manual entry" if status == "Present" else ""
    df.to_csv(ATTENDANCE_CSV, index=False)
    return True
