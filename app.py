import sys
import subprocess
import os
import tempfile
import asyncio
import threading
import uuid

# ✅ تثبيت المكتبات المطلوبة تلقائياً إذا لم تكن موجودة
for package in ["arabic-reshaper", "python-bidi", "pillow", "numpy", "moviepy", "pyppeteer", "flask"]:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

from flask import Flask, render_template, request, send_file, jsonify
from moviepy.editor import AudioFileClip, VideoClip
from PIL import Image
import numpy as np
import arabic_reshaper
from bidi.algorithm import get_display
from pyppeteer import launch

app = Flask(__name__)
progress_value = {}
jobs_results = {}

# ✅ الصفحة الرئيسية تعرض index.html من مجلد templates
@app.route("/")
def home():
    return render_template("index.html")


# -------------------------------
# تابع إنشاء صورة للنص بالعربية
# -------------------------------
async def render_arabic_text(text, width, height, font_size):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)

    font_path = os.path.abspath("NotoNaskhArabic-VariableFont_wght.ttf")
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"❌ ملف الخط غير موجود: {font_path}")

    html_content = f"""
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <style>
            @font-face {{
                font-family: 'MyArabicFont';
                src: url('file://{font_path}') format('truetype');
            }}
            body {{
                margin: 0;
                background: transparent;
                display: flex;
                align-items: center;
                justify-content: center;
                width: {width}px;
                height: {height}px;
            }}
            p {{
                font-family: 'MyArabicFont', sans-serif;
                font-size: {font_size}px;
                color: white;
                text-align: center;
                white-space: pre-line;
            }}
        </style>
    </head>
    <body>
        <p>{bidi_text}</p>
    </body>
    </html>
    """

    html_file = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    html_file.write(html_content.encode("utf-8"))
    html_file.close()

    browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
    page = await browser.newPage()
    await page.setViewport({"width": width, "height": height})
    await page.goto(f"file://{html_file.name}")
    screenshot_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    await page.screenshot({'path': screenshot_path, 'omitBackground': True})
    await browser.close()

    return screenshot_path


# -------------------------------
# تابع إنشاء الفيديو
# -------------------------------
def process_video(job_id, audio_path, video_text):
    try:
        audio_clip = AudioFileClip(audio_path)
        width, height = 1280, 720

        text_image_path = asyncio.get_event_loop().run_until_complete(
            render_arabic_text(video_text, width, height, 80)
        )
        text_img = Image.open(text_image_path).convert("RGBA")

        def create_frame(t):
            progress_value[job_id] = int((t / audio_clip.duration) * 100)
            return np.array(Image.new("RGB", (width, height), color=(50, 50, 50)))

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
