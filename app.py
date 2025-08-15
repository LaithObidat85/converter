import sys
import subprocess
import os

# ✅ التأكد من تثبيت المكتبات المطلوبة
for package in ["arabic-reshaper", "python-bidi", "pillow", "numpy", "moviepy"]:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

from flask import Flask, render_template, request, send_file, jsonify
from moviepy.editor import AudioFileClip, VideoClip
from PIL import Image, ImageDraw, ImageFont, ImageOps
import numpy as np
import math

# مكتبات دعم العربية
import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__)
progress_value = 0

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

    # 📌 مسار الخط
    font_path = os.path.join(os.path.dirname(__file__), "NotoNaskhArabic-VariableFont_wght.ttf")
    print(f"✅ الخط المستخدم: {font_path}")

    def blend_colors(c1, c2, ratio):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * ratio) for i in range(3))

    def draw_text_with_pillow(text, font_size, image_width, image_height):
        """إنشاء صورة نص باستخدام Pillow مع دعم العربية + مسافة بين الأسطر"""
        reshaped_text = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped_text)

        lines = bidi_text.split("\n")
        img = Image.new("RGBA", (image_width, image_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype(font_path, font_size)
        except:
            return img

        # حساب الارتفاع الكلي للنص مع المسافات
        total_height = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            h = bbox[3] - bbox[1]
            line_heights.append(h)
            total_height += h + 20  # 20 بكسل مسافة بين الأسطر
        total_height -= 20

        y = (image_height - total_height) / 2
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (image_width - text_width) / 2
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
            y += line_heights[i] + 20

        # قلب الصورة أفقياً لعكس اتجاه النص
        img = ImageOps.mirror(img)
        return img

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
        text_img = draw_text_with_pillow(video_text, 80, width, height)
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
