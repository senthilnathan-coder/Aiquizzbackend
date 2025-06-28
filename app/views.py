from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from mongoengine.errors import DoesNotExist
from datetime import datetime
from bson import ObjectId
import base64, tempfile, os, cv2, requests
from bs4 import BeautifulSoup
from faster_whisper import WhisperModel
from PyPDF2 import PdfReader
from pptx import Presentation
from openpyxl import load_workbook
import mammoth
from app.models import *
from app2.models import *
from app.serializers import *
from payments.models import *
import google.generativeai as genai
import threading

genai.configure(api_key=settings.GEMINI_API_KEY)
whisper_model = WhisperModel("tiny", compute_type="float32", device="cpu")

def extract_text(file, extractor):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp:
        for chunk in file.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        return extractor(tmp_path)
    finally:
        os.remove(tmp_path)

def extract_url_text(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        [tag.decompose() for tag in soup(["script", "style"])]
        return '\n'.join(line.strip() for line in soup.get_text(separator='\n').splitlines() if line.strip())
    except Exception as e:
        raise Exception(f"Error extracting URL text: {str(e)}")

def extract_frame(video_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(video_file.read())
        tmp_path = tmp.name

    cap = cv2.VideoCapture(tmp_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) // 2)
    success, frame = cap.read()
    cap.release()
    os.remove(tmp_path)

    if not success:
        raise Exception("Could not read frame from video")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
        frame_path = tmp_img.name
        cv2.imwrite(frame_path, frame)

    with open(frame_path, "rb") as f:
        image_data = f.read()
    os.remove(frame_path)
    return image_data, "image/jpeg"

def transcribe_audio(path):
    segments, _ = whisper_model.transcribe(path, beam_size=1, language=None)
    return ' '.join(s.text.strip() for s in segments if s.text.strip())

def extract_pdf_text(path):
    return '\n'.join(page.extract_text() for page in PdfReader(path).pages if page.extract_text())

def extract_word_text(path):
    with open(path, "rb") as docx_file:
        return mammoth.extract_raw_text(docx_file).value

def extract_ppt_text(path):
    return '\n'.join(shape.text for slide in Presentation(path).slides for shape in slide.shapes if hasattr(shape, "text"))

def extract_excel_text(path):
    wb = load_workbook(path, read_only=True)
    return '\n'.join(str(cell.value) for sheet in wb.worksheets for row in sheet.iter_rows() for cell in row if cell.value)
def parse_questions(response_text, question_type='both', limit=25):
    questions, topic = [], 'general'
    try:
        lines = response_text.strip().splitlines()
        for line in lines:
            if line.lower().startswith('topic:'):
                topic = line.split(':', 1)[1].strip()
                break

        blocks = response_text.strip().split("Q")[1:]

        for block in blocks:
            if len(questions) >= limit:
                break  # ✅ Enforce the question count limit

            lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
            if not lines:
                continue

            q_text = lines[0].split(':', 1)[1].strip() if ':' in lines[0] else lines[0]
            answer_line = next((l for l in lines if l.lower().startswith(('answer:', 'ans:', 'a:'))), None)
            options = [l[2:].strip() for l in lines[1:] if l.lower().startswith(('a.', 'b.', 'c.', 'd.'))]
            # MCQ
            if len(options) == 4 and answer_line:
                idx_char = answer_line.split(':')[1].strip().upper()[0]
                idx = ord(idx_char) - ord('A')
                if 0 <= idx < 4 and question_type in ['mcq', 'both']:
                    questions.append({
                        'question': q_text,
                        'options': options,
                        'answer': options[idx],
                        'topic': topic,
                        'type': 'mcq'
                    })
                    continue
            # True/False
            if answer_line:
                a_text = answer_line.split(':')[1].strip().lower()
                if a_text in ['true', 't', 'a'] and question_type in ['true_false', 'both']:
                    questions.append({
                        'question': q_text,
                        'options': ['True', 'False'],
                        'answer': 'True',
                        'topic': topic,
                        'type': 'true_false'
                    })
                elif a_text in ['false', 'f', 'b'] and question_type in ['true_false', 'both']:
                    questions.append({
                        'question': q_text,
                        'options': ['True', 'False'],
                        'answer': 'False',
                        'topic': topic,
                        'type': 'true_false'
                    })
    except Exception as e:
        print(f"Error parsing questions: {str(e)}")
    return questions[:limit]


class MultimodalQuizView(APIView):
    def get(self, request, pk):
        try:
            User.objects.get(id=pk)
            return Response({
                'message': 'POST with content to generate quiz',
                'supported_content_types': ['text', 'image', 'audio', 'video', 'pdf', 'word', 'ppt', 'excel', 'url'],
                'difficulty_levels': ['easy', 'medium', 'hard'],
                'question_types': ['mcq', 'true_false']
            })
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, pk):
        token_key = request.data.get('token')
        if not token_key:
            return Response({'status': 0, 'error': 'Token is required'}, status=400)

        try:
            token = AuthToken.objects.only('token', 'user', 'expires_at').get(token=token_key, user=pk)
            if token.expires_at < datetime.utcnow():
                return Response({'error': 'Token expired'}, status=401)

            user = token.user
            if user.role != 'user':
                return Response({'status': 0, 'error': 'Access denied: not a user'}, status=403)

            subscription = UserSubscription.objects(user=user.id, is_active=True).order_by('-start_date').first()
            if not subscription or (subscription.end_date and subscription.end_date < datetime.utcnow()):
                if subscription:
                    subscription.is_active = False
                    subscription.save()
                return Response({'error': 'No active or expired subscription'}, status=403)
            if subscription.remaining_credits <= 0:
                return Response({'error': 'No remaining quiz credits'}, status=403)

            data, files = request.data, request.FILES
            content_text = data.get('text', '').strip()
            url = data.get('url')
            difficulty = data.get('difficulty', 'medium').lower()
            question_type = data.get('question_type', 'both').lower()
            language = data.get('language', 'en')
            number_question = int(data.get('number_question', 10))

            if not (1 <= number_question <= 25):
                return Response({'error': 'number_question must be between 1 to 25'}, status=400)
            if not any([content_text, *files.values(), url]):
                return Response({'error': 'No input content'}, status=400)

            language_map = {
                'en': 'English', 'ta': 'தமிழ்', 'hi': 'हिन्दी', 'za': 'Afrikaans', 'de': 'Deutsch',
                'es': 'Español', 'ph': 'Filipino', 'fr': 'Français', 'it': 'Italiano', 'tr': 'Turkish',
                'ru': 'Русский', 'ae': 'العربية', 'jp': '日本語', 'kr': '한국어', 'ms': 'Malay'
            }
            lang_name = language_map.get(language, language.lower())

            prompt_base = (
                f"You are an AI quiz generator. Your task is to generate exactly {number_question} quiz questions "
                f"based on the content provided. The difficulty level should be '{difficulty}'.\n\n"
                "Rules you must follow:\n"
                f"1. You MUST generate exactly {number_question} questions. No more, no less.\n"
                f"2. Number each question exactly as Q1, Q2, ..., Q{number_question} using 'Q<number>:'.\n"
                "3. Do not include explanations, just questions, options, and answers.\n"
                "4. Use the exact format as shown below.\n"
                f"5. Language of quiz must be strictly {lang_name}.\n"
            )

            if question_type == "mcq":
                prompt_base += (
                    "All questions must be Multiple Choice Questions (MCQs).\n"
                    "Format:\n"
                    "Topic: <topic>\n"
                    "Q1: <question text>\nA. <option>\nB. <option>\nC. <option>\nD. <option>\nAnswer: <correct option letter>\n...\n"
                )
            elif question_type == "true_false":
                prompt_base += (
                    "All questions must be True or False.\n"
                    "Format:\n"
                    "Topic: <topic>\n"
                    "Q1: <question text>\nAnswer: True/False\n...\n"
                )
            else:
                prompt_base += (
                    "Mix both MCQ and True/False questions.\n"
                    "Format:\n"
                    "Topic: <topic>\n"
                    "MCQ:\nQ1: <question>\nA. <option>\nB. <option>\nC. <option>\nD. <option>\nAnswer: <correct option letter>\n"
                    "True/False:\nQ2: <question>\nAnswer: True/False\n...\n"
                )

            prompt = prompt_base + f"\n\nText: {content_text}\n"
            parts = [{"text": prompt}]

            for label, field, extractor in [
                ("audio", 'audio', transcribe_audio),
                ("pdf", 'pdf', extract_pdf_text),
                ("word", 'word', extract_word_text),
                ("ppt", 'ppt', extract_ppt_text),
                ("excel", 'excel', extract_excel_text),
            ]:
                if files.get(field):
                    try:
                        text = extract_text(files[field], extractor)
                        parts.append({"text": f"Additional context from {label}: {text}"})
                    except Exception as e:
                        return Response({'error': f'{label} extraction failed: {str(e)}'}, status=400)

            if url:
                try:
                    text = extract_url_text(url)
                    parts.append({"text": f"Extracted from URL: {text}"})
                except Exception as e:
                    return Response({'error': f'URL error: {str(e)}'}, status=400)

            if image := files.get('image'):
                parts.append({"inline_data": {"mime_type": image.content_type, "data": base64.b64encode(image.read()).decode()}})
            if video := files.get('video'):
                frame, mime = extract_frame(video)
                parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(frame).decode()}})

            response = genai.GenerativeModel("models/gemini-2.5-flash").generate_content(parts)
            questions = parse_questions(response.text, question_type, limit=number_question)

            if not questions or len(questions) < number_question:
                return Response({
                    'error': f'Only {len(questions)} out of {number_question} questions were generated. Try different content or lower difficulty.'
                }, status=400)

            topic = questions[0].get('topic', 'general')
            quiz_data = {
                'user': str(user.id),
                'title': f"Quiz on {topic}",
                'questions': questions,
                'number_question': len(questions),
                'difficulty': difficulty,
                'question_type': question_type,
                'content_type': [k for k in ['text', 'image', 'audio', 'video', 'pdf', 'word', 'ppt', 'excel', 'url'] if data.get(k) or files.get(k)],
                'topics': [topic]
            }

            serializer = QuizSerializer(data=quiz_data)
            if serializer.is_valid():
                quiz = serializer.save()
                subscription.remaining_credits -= 1
                subscription.save()
            else:
                return Response({'message': 'Invalid quiz data'}, status=400)

            # ✅ Flashcard generation
            flashcard_prompt = (
                f"Generate a list of flashcards for the topic of \"{topic}\". "
                "Each flashcard should have a term and a concise definition. "
                "Format the output as a list of \"Term: Definition\" pairs, one per line. "
                f"Language must be {lang_name} only. Return only the list."
            )
            flashcard_parts = [{"text": flashcard_prompt}]
            flashcard_response = genai.GenerativeModel("models/gemini-2.5-flash").generate_content(flashcard_parts)
            flashcard_text = flashcard_response.text or ""

            return Response({
                'message': 'Quiz generated',
                'user_id': str(user.id),
                'quiz_id': str(quiz.id),
                'topics': topic,
                'questions': [{'question': q['question'], 'options': q['options'], 'answer': q['answer']} for q in questions],
                'flashcards': flashcard_text.strip(),
                'remaining_credits': subscription.remaining_credits
            })

        except Exception as e:
            return Response({'error': str(e)}, status=500)



class SubmitQuizView(APIView):
    def post(self, request, pk):
        try:
            user = User.objects.get(id=ObjectId(pk))
            quiz_id = request.data.get('quiz_id')
            user_answers = request.data.get('user_answers')  # e.g., {"0": "True", "1": "False"}

            if not quiz_id or not user_answers:
                return Response({'error': 'Missing quiz_id or user_answers'}, status=400)

            quiz = Quiz.objects.get(id=ObjectId(quiz_id))

            score = 0
            correct_count = 0
            evaluated_questions = []
            answer_texts = []

            for idx, question in enumerate(quiz.questions):
                key = str(idx)  # Ensure index is used as string
                selected_answer = user_answers.get(key)

                correct_answer = question.get('answer')
                options = question.get('options', [])
                question_text = question.get('question')

                is_correct = False
                if selected_answer is not None:
                    is_correct = selected_answer == correct_answer
                    if is_correct:
                        score += 1
                        correct_count += 1

                    evaluated_questions.append({
                        'question_id': key,
                        'question': question_text,
                        'options': options,
                        'correct_answer': correct_answer,
                        'selected_answer': selected_answer,
                        'is_correct': is_correct
                    })
                    answer_texts.append(selected_answer)

            if not evaluated_questions:
                return Response({'error': 'No questions evaluated'}, status=400)

            attempt_data = {
                'user': str(user.id),
                'quiz': str(quiz.id),
                'questions': evaluated_questions,
                'number_question': len(quiz.questions),
                'user_answers': answer_texts,
                'score': score,
                'difficulty': quiz.difficulty,
                'question_type': quiz.question_type,
                'topics': quiz.topics
            }

            serializer = QuizAttemptSerializer(data=attempt_data)
            if serializer.is_valid():
                attempt = serializer.save()
                return Response({
                    'message': 'Quiz submitted',
                    'score': score,
                    'total_questions': len(quiz.questions),
                    'correct_answers': correct_count,
                    'quiz_attempt_id': str(attempt.id),    
                })
            else:
                return Response({
                    'message': 'Invalid attempt data',
                    'errors': serializer.errors
                }, status=400)

        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except Quiz.DoesNotExist:
            return Response({'error': 'Quiz not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)