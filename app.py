import sys
import subprocess
import os
import threading
import uuid
import numpy as np
from flask import Flask, render_template, request, send_file, jsonify
from moviepy.editor import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageFont

# ✅ تثبيت المكتبات المطلوبة تلقائياً إذا لم تكن موجودة
for package in ["pillow", "numpy", "moviepy", "flask", "arabic-reshaper", "python-bidi"]:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__)
progress_value = {}
jobs_results = {}

# ✅ الصفحة الرئيسية
@app.route("/")
def home():
    return render_template("index.html")

# -------------------------------
# تابع إنشاء صورة نص عربي باستخدام Pillow
# -------------------------------
def render_arabic_text(text, width, height, font_size):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)

    font_path = os.path.abspath("NotoNaskhArabic-VariableFont_wght.ttf")
    if not os.path.exists(font_path):
        raise FileNotFoundError("❌ ملف الخط NotoNaskhArabic غير موجود")

    img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)

    text_w, text_h = draw.textsize(bidi_text, font=font)
    position = ((width - text_w) // 2, (height - text_h) // 2)
    draw.text(position, bidi_text, font=font, fill=(255, 255, 255, 255))

    tmp_path = f"text_{uuid.uuid4()}.png"
    img.save(tmp_path)
    return tmp_path

# -------------------------------
# تابع إنشاء الفيديو
# -------------------------------
def process_video(job_id, audio_path, video_text):
    try:
        audio_clip = AudioFileClip(audio_path)
        width, height = 1280, 720

        text_image_path = render_arabic_text(video_text, width, height, 60)
        text_img = Image.open(text_image_path).convert("RGBA")

        def create_frame(t):
            progress_value[job_id] = int((t / audio_clip.duration) * 100)
            frame = Image.new("RGB", (width, height), color=(50, 50, 50))
            frame.paste(text_img, (0, 0), text_img)
            return np.array(frame)

        output_path = f"converted_{job_id}.mp4"
        video_clip = VideoClip(make_frame=create_frame, duration=audio_clip.duration)
        video_clip.set_audio(audio_clip).write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )

        progress_value[job_id] = 100
        jobs_results[job_id] = output_path

    except Exception as e:
        jobs_results[job_id] = f"❌ خطأ: {str(e)}"
        progress_value[job_id] = -1

# -------------------------------
# API Endpoints
# -------------------------------
@app.route('/convert', methods=['POST'])
def convert():
    try:
        audio_file = request.files.get('audio')
        video_text = request.form.get("text", "").strip()
        if not audio_file:
            return jsonify({"error": "❌ لم يتم رفع أي ملف"}), 400

        audio_path = f"uploaded_{uuid.uuid4()}.wav"
        audio_file.save(audio_path)

        job_id = str(uuid.uuid4())
        progress_value[job_id] = 0

        threading.Thread(target=process_video, args=(job_id, audio_path, video_text)).start()

        return jsonify({"job_id": job_id, "status": "started"})

    except Exception as e:
        return jsonify({"error": f"❌ خطأ غير متوقع: {str(e)}"}), 500

@app.route('/progress/<job_id>')
def progress(job_id):
    return jsonify({"progress": progress_value.get(job_id, 0)})

@app.route('/result/<job_id>')
def result(job_id):
    result = jobs_results.get(job_id)
    if not result:
        return jsonify({"message": "❌ لم يتم العثور على النتيجة"}), 404
    if result.endswith(".mp4") and os.path.exists(result):
        return send_file(result, as_attachment=True)
    return jsonify({"message": result})

# -------------------------------
# تشغيل السيرفر
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
