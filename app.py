import sys
import subprocess
import tempfile

# ✅ التأكد من تثبيت المكتبات المطلوبة
for package in ["arabic-reshaper", "python-bidi"]:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

from flask import Flask, render_template, request, send_file, jsonify
from moviepy.editor import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import math
import os

# مكتبات دعم العربية
import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__)
progress_value = 0  # لتتبع نسبة الإنجاز

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

    audio_file = request.files.get('audio')
    video_text = request.form.get("text", "No text provided").strip()

    if not audio_file:
        return "❌ لم يتم رفع أي ملف", 400

    # ✅ حفظ الملفات المؤقتة في /tmp على Render
    audio_path = os.path.join(tempfile.gettempdir(), "uploaded.wav")
    output_path = os.path.join(tempfile.gettempdir(), "converted_video.mp4")
    audio_file.save(audio_path)

    # ✅ التحقق من نوع الملف
    print(f"📂 Uploaded file mimetype: {audio_file.mimetype}")
    if not audio_file.mimetype in ["audio/wav", "audio/x-wav"]:
        return "❌ الملف المرسل ليس بصيغة WAV. تحقق من عملية التحويل في المتصفح.", 400

    # ✅ قراءة الملف الصوتي
    try:
        audio_clip = AudioFileClip(audio_path)
    except Exception as e:
        return f"❌ خطأ في قراءة الملف الصوتي: {str(e)}", 500

    width, height = 1280, 720
    colors = [(30, 30, 120), (200, 50, 50), (50, 200, 100)]

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

        image = Image.new("RGB", (width, height), color=color)
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.truetype("arial-unicode-ms.ttf", 80)
        except:
            font = ImageFont.load_default()

        # 🔹 دعم العربية سطر-بسطر
        video_text_clean = video_text.replace("\r\n", "\n").replace("\r", "\n")
        raw_lines = video_text_clean.split("\n")

        lines = []
        for raw in raw_lines:
            clean = ''.join(ch for ch in raw if ch.isprintable())
            if any('\u0600' <= ch <= '\u06FF' for ch in clean):
                reshaped = arabic_reshaper.reshape(clean)
                bidi_line = get_display(reshaped)
            else:
                bidi_line = clean
            lines.append(bidi_line)

        line_heights = []
        max_width = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            line_heights.append(h)
            if w > max_width:
                max_width = w

        total_height = sum(line_heights) + (len(lines) - 1) * 20
        current_y = (height - total_height) // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            x = (width - w) // 2
            draw.text((x, current_y), line, font=font, fill="white")
            current_y += h + 20

        return np.array(image)

    try:
        video_clip = VideoClip(make_frame=create_frame, duration=audio_clip.duration)
        video_clip.set_audio(audio_clip).write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
    except Exception as e:
        return f"❌ خطأ أثناء إنشاء الفيديو: {str(e)}", 500

    progress_value = 100
    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
