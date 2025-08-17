# باقي الاستيرادات والكود كما هو عندك 👇
import sys
import subprocess
import os
import tempfile
import asyncio
import threading
import uuid

for package in ["arabic-reshaper", "python-bidi", "pillow", "numpy", "moviepy", "pyppeteer"]:
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

# ================== render_arabic_text ==================
async def render_arabic_text(text, width, height, font_size):
    app.logger.info("▶️ دخل render_arabic_text")
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)

    font_path = os.path.abspath("NotoNaskhArabic-VariableFont_wght.ttf")
    if not os.path.exists(font_path):
        app.logger.error(f"❌ ملف الخط غير موجود: {font_path}")
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
    app.logger.info(f"📄 HTML جاهز: {html_file.name}")

    browser = await launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
    page = await browser.newPage()
    await page.setViewport({"width": width, "height": height})
    await page.goto(f"file://{html_file.name}")
    screenshot_path = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
    await page.screenshot({'path': screenshot_path, 'omitBackground': True})
    await browser.close()

    app.logger.info(f"🖼️ تم إنشاء صورة النص: {screenshot_path}")
    return screenshot_path


# ================== process_video ==================
def process_video(job_id, audio_path, video_text):
    try:
        app.logger.info(f"▶️ بدأ process_video للملف {audio_path}")
        audio_clip = AudioFileClip(audio_path)
        width, height = 1280, 720

        text_image_path = asyncio.get_event_loop().run_until_complete(
            render_arabic_text(video_text, width, height, 80)
        )
        app.logger.info(f"🖼️ صورة النص جاهزة: {text_image_path}")
        text_img = Image.open(text_image_path).convert("RGBA")

        def create_frame(t):
            progress_value[job_id] = int((t / audio_clip.duration) * 100)
            return np.array(Image.new("RGB", (width, height), color=(50, 50, 50)))

        output_path = f"converted_{job_id}.mp4"
        app.logger.info(f"🎥 كتابة الفيديو إلى {output_path}")
        video_clip = VideoClip(make_frame=create_frame, duration=audio_clip.duration)
        video_clip.set_audio(audio_clip).write_videofile(
            output_path, fps=24, codec="libx264", audio_codec="aac"
        )

        progress_value[job_id] = 100
        jobs_results[job_id] = output_path
        app.logger.info(f"✅ اكتمل إنشاء الفيديو: {output_path}")

    except Exception as e:
        jobs_results[job_id] = f"❌ خطأ: {str(e)}"
        progress_value[job_id] = -1
        app.logger.error(f"❌ فشل process_video: {e}")


# ================== convert API ==================
@app.route('/convert', methods=['POST'])
def convert():
    try:
        app.logger.info("▶️ دخل convert")
        audio_file = request.files.get('audio')
        video_text = request.form.get("text", "").strip()
        if not audio_file:
            app.logger.error("❌ لم يتم رفع أي ملف صوتي")
            return jsonify({"error": "❌ لم يتم رفع أي ملف"}), 400

        audio_path = f"uploaded_{uuid.uuid4()}.wav"
        audio_file.save(audio_path)
        app.logger.info(f"📥 تم حفظ الملف: {audio_path}")

        job_id = str(uuid.uuid4())
        progress_value[job_id] = 0
        app.logger.info(f"🆔 Job ID = {job_id}")

        threading.Thread(target=process_video, args=(job_id, audio_path, video_text)).start()

        return jsonify({"job_id": job_id, "status": "started"})

    except Exception as e:
        app.logger.error(f"❌ خطأ داخل convert: {e}")
        return jsonify({"error": f"❌ خطأ غير متوقع: {str(e)}"}), 500


# ================== progress API ==================
@app.route('/progress/<job_id>', methods=['GET'])
def progress(job_id):
    """إرجاع حالة التقدم الحالية للفيديو"""
    if job_id in progress_value:
        return jsonify({"progress": progress_value[job_id]})
    else:
        return jsonify({"error": "❌ Job ID غير موجود"}), 404
