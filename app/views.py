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
import google.generativeai as genai

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
    segments, _ = whisper_model.transcribe(path, beam_size=5, language=None)
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

def parse_questions(response_text, question_type='mcq'):
    questions, topic = [], 'general'
    try:
        lines = response_text.strip().splitlines()
        for line in lines:
            if line.lower().startswith('topic:'):
                topic = line.split(':', 1)[1].strip()
                break
        for block in response_text.strip().split("Q")[1:]:
            lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
            if not lines: continue
            q_text = lines[0].split(':', 1)[1].strip() if ':' in lines[0] else lines[0]
            answer_line = next((l for l in lines if l.lower().startswith(('answer:', 'ans:', 'a:'))), None)
            if question_type == 'mcq':
                options = [l[2:].strip() for l in lines[1:] if l.lower().startswith(('a.', 'b.', 'c.', 'd.'))]
                if len(options) == 4 and answer_line:
                    idx = ord(answer_line.split(':')[1].strip().upper()[0]) - ord('A')
                    if 0 <= idx < 4:
                        questions.append({'question': q_text, 'options': options, 'answer': options[idx], 'topic': topic})
            elif question_type == 'true_false' and answer_line:
                a_text = answer_line.split(':')[1].strip().lower()
                idx = 0 if a_text in ['true', 't', 'a'] else 1 if a_text in ['false', 'f', 'b'] else -1
                if idx in [0, 1]:
                    questions.append({'question': q_text, 'options': ['True', 'False'], 'answer': ['True', 'False'][idx], 'topic': topic})
    except Exception as e:
        print(f"Error parsing questions: {str(e)}")
    return questions


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
        try:
            token_key = request.data.get('token')
            if not token_key:
                return Response({'message': 'Token required'}, status=status.HTTP_400_BAD_REQUEST)
            token = UserToken.objects.get(token=token_key, user=pk)
            if token.expires_at < datetime.utcnow():
                return Response({'error': 'Token expired'}, status=status.HTTP_401_UNAUTHORIZED)

            user = token.user
            if not user.is_verified:
                return Response({'message':'user is not verified'},status=status.HTTP_400_BAD_REQUEST)
            # quiz_count=Quiz.objects(user=user).count()
            # if quiz_count >=10:
            #     last_payment=Payment.objects(user=user,is_paid=True).order_by('-payment_time').first()
            #     if not last_payment or last_payment.payment_time <user.last_quiz_created_at:
            #         return Response({
            #              'error': 'Free limit exceeded. Please pay ₹50 to generate the next quiz.',
            #             'payment_required': True,
            #             'amount': 50
            #         }, status=status.HTTP_402_PAYMENT_REQUIRED)
            
            data, files = request.data, request.FILES
            content_text = data.get('text', '').strip()
            url = data.get('url')
            difficulty = data.get('difficulty', 'medium')
            question_type = data.get('question_type', 'mcq')
            number_question = int(data.get('number_question', 10))
            if not (1 <= number_question <= 25):
                return Response({'error': 'number_question must be between 1 to 25'}, status=400)

            if not any([content_text, *files.values(), url]):
                return Response({'error': 'No input content'}, status=status.HTTP_400_BAD_REQUEST)

            prompt = f"You're an AI quiz generator. {difficulty.capitalize()} level. Identify main topic. Generate {number_question} {'MCQs' if question_type == 'mcq' else 'True/False'} questions."
            prompt += "\nFormat:\nTopic: <topic>\n\nQ: <question>\nA. <option>\n...\nAnswer: <correct>\n\nText: " + content_text
            parts = [{"text": prompt}]

            # Extract additional content
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

            response = genai.GenerativeModel("models/gemini-1.5-flash").generate_content(parts)
            questions = parse_questions(response.text, question_type)
            if not questions:
                return Response({'message': 'No questions generated'}, status=400)

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
            else:
                return Response({'message': 'Invalid quiz data'}, status=400)

            return Response({
                'message': 'Quiz generated',
                'user_id': str(user.id),
                'quiz_id': str(quiz.id),
                'topics': topic,
                'questions': [{'question': q['question'], 'options': q['options'], 'answer': q['answer']} for q in questions]
            })

        except Exception as e:
            return Response({'error': str(e)}, status=500)

class SubmitQuizView(APIView):
    def post(self, request, pk):
        try:
            user = User.objects.get(id=pk)
            quiz_id = request.data.get('quiz_id')
            user_answers = request.data.get('user_answers')

            if not quiz_id or not user_answers:
                return Response({'error': 'Missing quiz_id or answers'}, status=400)

            quiz = Quiz.objects.get(id=quiz_id)
            score, correct_count = 0, 0
            evaluated_questions, answer_texts = [], []

            for q in quiz.questions:
                qid = str(q.get('_id'))
                correct = q.get('answer')
                opts = q.get('options', [])
                selected = user_answers.get(qid)

                if selected is not None and 0 <= selected < len(opts):
                    chosen = opts[selected]
                    is_correct = chosen == correct
                    if is_correct: score += 1; correct_count += 1
                    evaluated_questions.append({
                        'question_id': qid, 'question': q.get('question'),
                        'options': opts, 'correct_answer': correct,
                        'selected_answer': chosen, 'is_correct': is_correct
                    })
                    answer_texts.append(chosen)

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
            else:
                return Response({'message': 'Invalid attempt data'}, status=400)

            return Response({
                'message': 'Quiz submitted',
                'score': score,
                'total_questions': len(quiz.questions),
                'correct_answers': correct_count,
                'quiz_attempt_id': str(attempt.id)
            })
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        except Quiz.DoesNotExist:
            return Response({'error': 'Quiz not found'}, status=404)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
