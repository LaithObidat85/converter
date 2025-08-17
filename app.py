# app.py
from flask import Flask, request, jsonify, send_file, render_template
import os
import uuid
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import numpy as np

app = Flask(__name__)

# مجلد لحفظ الملفات المؤقتة
UPLOAD_FOLDER = "uploads"
RESULTS_FOLDER = "results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULTS_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_audio_to_video():
    try:
        # استلام الملف والنص
        audio_file = request.files.get("audio")
        text = request.form.get("text", "")

        if not audio_file:
            return jsonify({"error": "لم يتم رفع أي ملف صوتي"}), 400

        # حفظ الملف الصوتي
        audio_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.wav")
        audio_file.save(audio_path)

        # تحميل الصوت
        audio_clip = AudioFileClip(audio_path)

        # إنشاء صورة بالنص باستخدام Pillow
        img_width, img_height = 1280, 720
        img = Image.new("RGB", (img_width, img_height), color="white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("arial.ttf", 40)
        text = text if text else "🎵 ملف صوتي تم تحويله إلى فيديو 🎵"

        # مركز النص
        w, h = draw.textsize(text, font=font)
        draw.text(((img_width - w) / 2, (img_height - h) / 2), text, fill="black", font=font)

        # حفظ الصورة المؤقتة
        img_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.png")
        img.save(img_path)

        # عمل فيديو من الصورة مع مدة الصوت
        img_clip = ImageClip(img_path).set_duration(audio_clip.duration)
        final_clip = img_clip.set_audio(audio_clip)

        # حفظ الفيديو النهائي
        output_path = os.path.join(RESULTS_FOLDER, f"{uuid.uuid4()}.mp4")
        final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")

        return send_file(output_path, as_attachment=True, download_name="converted_video.mp4")

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
