import sys
import subprocess
import os

# ✅ التأكد من تثبيت المكتبات المطلوبة
for package in ["arabic-reshaper", "python-bidi", "pycairo", "PyGObject"]:
    try:
        __import__(package.replace("-", "_"))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

from flask import Flask, render_template, request, send_file, jsonify
from moviepy.editor import AudioFileClip, VideoClip
from PIL import Image
import numpy as np
import math

# مكتبات دعم العربية
import arabic_reshaper
from bidi.algorithm import get_display

# مكتبات Pango + Cairo
import gi
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Pango, PangoCairo, cairo

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

    def draw_text_with_pango(text, font_size, image_width, image_height):
        """إنشاء صورة نص باستخدام Pango + Cairo مع دعم العربية"""
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, image_width, image_height)
        ctx = cairo.Context(surface)
        layout = PangoCairo.create_layout(ctx)

        # تفعيل دعم العربية
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)

        # إعدادات الخط
        font_desc = Pango.FontDescription(f"Noto Naskh Arabic {font_size}")
        layout.set_font_description(font_desc)
        layout.set_width(image_width * Pango.SCALE)
        layout.set_alignment(Pango.Alignment.CENTER)
        layout.set_text(bidi_text, -1)

        # تحديد موقع النص في منتصف الصورة
        ink_rect, logical_rect = layout.get_extents()
        text_height = logical_rect.height // Pango.SCALE
        ctx.set_source_rgb(1, 1, 1)
        ctx.move_to(0, (image_height - text_height) / 2)
        PangoCairo.show_layout(ctx, layout)

        return surface

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

        # خلفية
        bg_image = Image.new("RGB", (width, height), color=color)

        # نص
        text_surface = draw_text_with_pango(video_text, 80, width, height)
        text_data = text_surface.get_data()
        text_img = Image.frombuffer("RGBA", (width, height), text_data, "raw", "BGRA", 0, 1)

        # دمج النص مع الخلفية
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
