from flask import Flask, request, send_file, jsonify
import os
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import tempfile
import threading

app = Flask(__name__)

# ======================
# اختيار الخط العربي
# ======================
arial_path = os.path.join(os.path.dirname(__file__), "arial-unicode-ms.ttf")
noto_path = os.path.join(os.path.dirname(__file__), "NotoNaskhArabic-VariableFont_wght.ttf")

if os.path.exists(arial_path):
    font_path = arial_path
    print(f"✅ Using font: {os.path.basename(font_path)}")
elif os.path.exists(noto_path):
    font_path = noto_path
    print(f"✅ Using font: {os.path.basename(font_path)}")
else:
    raise FileNotFoundError("❌ No valid Arabic font found in the project directory!")

# ======================
# متغيرات التقدم
# ======================
progress = {"progress": 0}

def reset_progress():
    progress["progress"] = 0

# ======================
# دالة إنشاء صورة مع نص عربي
# ======================
def create_text_image(text, size=(1280, 720), fontsize=50):
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)

    img = Image.new('RGB', size, color='white')
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, fontsize)
    w, h = draw.textsize(bidi_text, font=font)
    draw.text(((size[0]-w)/2, (size[1]-h)/2), bidi_text, font=font, fill='black')
    return img

# ======================
# مسار التحويل
# ======================
@app.route('/convert', methods=['POST'])
def convert():
    reset_progress()

    audio_file = request.files['audio']
    text = request.form['text']

    with tempfile.TemporaryDirectory() as tempdir:
        audio_path = os.path.join(tempdir, "audio.wav")
        audio_file.save(audio_path)

        # إنشاء صورة للنص
        img = create_text_image(text)
        img_path = os.path.join(tempdir, "text.png")
        img.save(img_path)

        progress["progress"] = 30

        # تحويل الصورة إلى فيديو
        clip_img = ImageClip(img_path).set_duration(AudioFileClip(audio_path).duration)
        clip_audio = AudioFileClip(audio_path)

        progress["progress"] = 60

        # دمج الصوت والصورة
        final_clip = clip_img.set_audio(clip_audio)

        output_path = os.path.join(tempdir, "converted_video.mp4")
        final_clip.write_videofile(output_path, fps=24, codec='libx264', audio_codec='aac')

        progress["progress"] = 100

        return send_file(output_path, as_attachment=True)

# ======================
# مسار التقدم
# ======================
@app.route('/progress', methods=['GET'])
def get_progress():
    return jsonify(progress)

# ======================
# تشغيل السيرفر
# ======================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
