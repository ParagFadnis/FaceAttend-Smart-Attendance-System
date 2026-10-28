from flask import Flask, render_template, request, jsonify
import base64, os, threading, time
import cv2, numpy as np, pandas as pd
from face_recognition import (
    ATTENDANCE_CSV, recognize_face, mark_attendance,
    manual_mark_attendance, load_model_data, ensure_attendance_csv
)

app = Flask(__name__)
print("Loading face recognition model...")
student_registry, embeddings = load_model_data()
ensure_attendance_csv(embeddings.keys())
print(f"Loaded {len(embeddings)} student embeddings.")

state_lock = threading.Lock()
dwell_name = None
dwell_start = None
DWELL_SECONDS = 30

@app.route("/")
def index(): return render_template("index.html")

@app.route("/attendance")
def attendance_page(): return render_template("attendance.html")

@app.route("/students")
def students_page(): return render_template("students.html")

@app.route("/api/stats")
def stats():
    df = pd.read_csv(ATTENDANCE_CSV)
    total = len(df)
    present = int((df["Status"] == "Present").sum())
    return jsonify(total=total, present=present, absent=total-present,
                   percentage=round(present/total*100, 1) if total else 0)

@app.route("/api/attendance")
def attendance():
    return jsonify(pd.read_csv(ATTENDANCE_CSV).fillna("").to_dict(orient="records"))

@app.route("/api/students")
def students():
    items = []
    for name, path in sorted(student_registry.items()):
        rel = os.path.relpath(path, os.path.join(os.path.dirname(__file__), "student_photos"))
        items.append({"name": name, "photo": "/student_photos/" + rel.replace("\\", "/")})
    return jsonify(total=len(items), students=items)

@app.route("/student_photos/<path:filename>")
def student_photo(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.join(os.path.dirname(__file__), "student_photos"), filename)

@app.route("/api/recognize", methods=["POST"])
def recognize():
    global dwell_name, dwell_start
    data = request.get_json(silent=True) or {}
    image_data = data.get("image")
    if not image_data:
        return jsonify(success=False, error="No image received"), 400
    try:
        image_data = image_data.split(",", 1)[-1]
        raw = base64.b64decode(image_data)
        frame = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify(success=False, error="Invalid image"), 400

        results = recognize_face(frame, embeddings)
        if not results:
            with state_lock:
                dwell_name = dwell_start = None
            return jsonify(success=True, recognized=False, message="No face detected", results=[])

        best = max(results, key=lambda r: r["confidence"] if r["name"] != "Unknown" else -1)
        name, confidence = best["name"], best["confidence"]
        marked, elapsed = False, 0

        if name != "Unknown":
            with state_lock:
                now = time.time()
                if dwell_name != name:
                    dwell_name, dwell_start = name, now
                elapsed = int(now - dwell_start)
                if elapsed >= DWELL_SECONDS:
                    marked = mark_attendance(name, confidence)

        return jsonify(success=True, recognized=name != "Unknown",
                       name=name, confidence=confidence,
                       distance=best["distance"], bbox=best["bbox"],
                       dwell_seconds=elapsed, required_seconds=DWELL_SECONDS,
                       marked=marked, results=results)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route("/api/manual-attendance", methods=["POST"])
def manual():
    data = request.get_json(silent=True) or {}
    name, status = str(data.get("name","")).strip(), str(data.get("status","")).strip().title()
    if not name or status not in {"Present","Absent"}:
        return jsonify(success=False, error="Invalid name or status"), 400
    ok = manual_mark_attendance(name, status)
    return jsonify(success=ok, message=f"{name} marked {status}" if ok else f"Student '{name}' not found")

@app.route("/api/reset-dwell", methods=["POST"])
def reset():
    global dwell_name, dwell_start
    with state_lock:
        dwell_name = dwell_start = None
    return jsonify(success=True)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
