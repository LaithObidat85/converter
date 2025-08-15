from flask import Flask, request, send_file, jsonify, render_template
import os
from moviepy.editor import *
import arabic_reshaper
from bidi.algorithm import get_display

app = Flask(__name__)

# ===== إعداد الخط =====
FONT_PATH = os.path.join(os.path.dirname(__file__), "NotoNaskhArabic-VariableFont_wght.ttf")
if os.path.exists(FONT_PATH):
    print(f"✅ تم العثور على الخط: {os.path.basename(FONT_PATH)}")
else:
    print(f"⚠ لم يتم العثور على الخط، سيتم استخدام الخط الافتراضي Arial")

# ===== الصفحة الرئيسية =====
@app.route('/')
def index():
    return render_template("index.html")  # يتم تحميل الصفحة من مجلد templates

# ===== مسار التحويل =====
@app.route('/convert', methods=['POST'])
def convert():
    audio_file = request.files['audio']
    text = request.form['text']

    # تجهيز النص العربي
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)

    # قراءة ملف الصوت
    audio_path = "uploaded_audio.wav"
    audio_file.save(audio_path)
    audioclip = AudioFileClip(audio_path)

    # إنشاء النص على الفيديو
    txt_clip = TextClip(
        bidi_text,
        fontsize=60,
        font=FONT_PATH if os.path.exists(FONT_PATH) else "Arial",
        color='white',
        size=(1280, 720),
        method='caption'
    ).set_duration(audioclip.duration)

    # دمج النص والصوت في فيديو
    video = CompositeVideoClip([txt_clip])
    video = video.set_audio(audioclip)

    output_path = "converted_video.mp4"
    video.write_videofile(output_path, codec="libx264", audio_codec="aac")

    return send_file(output_path, as_attachment=True)

# ===== تشغيل السيرفر =====
if __name__ == '__main__':
    app.run(debug=True)
