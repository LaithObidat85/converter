import sys
import subprocess
import os
import tempfile
import asyncio

# ✅ التأكد من تثبيت المكتبات المطلوبة
for package in ["arabic-reshaper", "python-bidi", "pillow", "numpy", "moviepy", "pyppeteer"]:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

from flask import Flask, render_template, request, send_file, jsonify
from moviepy.editor import AudioFileClip, VideoClip
from PIL import Image
import numpy as np
import math
import arabic_reshaper
from bidi.algorithm import get_display
from pyppeteer import launch

app = Flask(__name__)
progress_value = 0

async def render_arabic_text(text, width, height, font_size):
    """إنشاء صورة PNG للنص العربي باستخدام Puppeteer وخط عربي محلي"""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)

    # مسار الخط بجانب ملف app.py
    font_path = os.path.abspath("NotoNaskhArabic-VariableFont_wght.ttf")

    # فحص وجود الخط
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

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/progress')
def progress():
    return jsonify({"progress": progress_value})

@app.route('/convert', methods=['POST'])
def convert():
    global progress_value
    progress_value = 0

    audio_file = request.files['audio']
    video_text = request.form.get("text", "No text provided").strip()

    if not audio_file:
        return "❌ لم يتم رفع أي ملف"

    audio_path = "uploaded.wav"
    audio_file.save(audio_path)
    audio_clip = AudioFileClip(audio_path)

    width, height = 1280, 720
    colors = [(30, 30, 120), (200, 50, 50), (50, 200, 100)]

    async def prepare_text_image():
        return await render_arabic_text(video_text, width, height, 80)

    text_image_path = asyncio.get_event_loop().run_until_complete(prepare_text_image())
    text_img = Image.open(text_image_path).convert("RGBA")

    def blend_colors(c1, c2, ratio):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * ratio) for i in range(3))

    def create_frame(t):
        global progress_value
        progress_value = int((t / audio_clip.duration) * 100)

        num_colors = len(colors)
        cycle_time = 6
        total_cycle = num_colors * cycle_time
        time_in_cycle = t % total_cycle

        current_index = int(time_in_cycle // cycle_time)
        next_index = (current_index + 1) % num_colors
        ratio = (time_in_cycle % cycle_time) / cycle_time

        pulse = (math.sin(2 * math.pi * t / 4) + 1) / 2
        base_color = blend_colors(colors[current_index], colors[next_index], ratio)
        color = tuple(int(c * (0.7 + 0.3 * pulse)) for c in base_color)

        bg_image = Image.new("RGB", (width, height), color=color)
        bg_image.paste(text_img, (0, 0), text_img)

        return np.array(bg_image)

    video_clip = VideoClip(make_frame=create_frame, duration=audio_clip.duration)
    output_path = "converted_video.mp4"
    video_clip.set_audio(audio_clip).write_videofile(
        output_path, fps=24, codec="libx264", audio_codec="aac"
    )

    progress_value = 100
    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
