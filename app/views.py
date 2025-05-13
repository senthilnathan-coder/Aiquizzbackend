from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai
import base64
import whisper
import tempfile
import os
import json
from moviepy import VideoFileClip
from django.conf import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
whisper_model = whisper.load_model("base")

def extract_frame(video_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(video_file.read())
        tmp_path = tmp.name

    clip = VideoFileClip(tmp_path)
    frame_path = tmp_path + "_frame.jpg"
    clip.save_frame(frame_path, t=clip.duration // 2)

    with open(frame_path, "rb") as f:
        data = f.read()

    os.remove(tmp_path)
    os.remove(frame_path)
    return data, "image/jpeg"

def transcribe_audio(audio_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name

    result = whisper_model.transcribe(tmp_path)
    os.remove(tmp_path)
    return result["text"]

def parse_questions(response_text):
    questions = []
    blocks = response_text.strip().split("Q")[1:]
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 6:
            continue
        question_text = lines[0].strip(": ").strip()
        options = [line.strip()[2:].strip() for line in lines[1:5]]
        answer_line = lines[5].strip()
        correct_letter = answer_line.split(":")[-1].strip()
        correct_index = ord(correct_letter.upper()) - ord('A')
        questions.append({
            'question': question_text,
            'options': options,
            'answer': options[correct_index] if 0 <= correct_index < len(options) else ''
        })
    return questions

@csrf_exempt
def generate_multimodal_quiz(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed.'}, status=405)

    try:
        content_text = request.POST.get('content', '')
        image = request.FILES.get('image')
        audio = request.FILES.get('audio')
        video = request.FILES.get('video')

        prompt = f"""
You're an AI quiz generator.
Based on the following content (text/audio/video/image), generate 5 multiple choice questions with 4 options.
Format strictly like:
Q: <question>
A. <option>
B. <option>
C. <option>
D. <option>
Answer: <correct_option_letter>

Text: {content_text}
"""

        parts = [{"text": prompt}]

        if image:
            img_data = image.read()
            parts.append({
                "inline_data": {
                    "mime_type": image.content_type,
                    "data": base64.b64encode(img_data).decode()
                }
            })

        if audio:
            transcribed = transcribe_audio(audio)
            parts.append({"text": f"Transcribed audio: {transcribed}"})

        if video:
            frame_data, mime = extract_frame(video)
            parts.append({
                "inline_data": {
                    "mime_type": mime,
                    "data": base64.b64encode(frame_data).decode()
                }
            })

        model = genai.GenerativeModel("models/gemini-1.5-flash")
        response = model.generate_content(parts)
        output = response.text
        questions = parse_questions(output)

        return JsonResponse({'questions': questions})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
