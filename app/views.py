from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
import google.generativeai as genai
import base64
import tempfile
import os
from django.conf import settings
from app.models import *
from mongoengine.errors import DoesNotExist, ValidationError
from datetime import datetime, timedelta
import cv2
import requests
from bs4 import BeautifulSoup
from faster_whisper import WhisperModel
from PyPDF2 import PdfReader
from pptx import Presentation
from openpyxl import load_workbook
from app.serializers import *
import mammoth
import tempfile
import os
from app2.models import *

genai.configure(api_key=settings.GEMINI_API_KEY)
whisper_model = WhisperModel("tiny", compute_type="float32",device="cpu")

def extract_url_text(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = '\n'.join(
            line.strip() for line in soup.get_text(separator='\n').splitlines() if line.strip()
        )
        if not text:
            raise ValueError("No text content found in URL")
        return text
    except Exception as e:
        raise Exception(f"Error extracting URL text: {str(e)}")

def extract_frame(video_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(video_file.read())
        tmp_path = tmp.name

    cap = cv2.VideoCapture(tmp_path)
    mid_frame = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) // 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_frame)
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

def transcribe_audio(audio_file):
    try:
        suffix = os.path.splitext(audio_file.name)[1] or '.mp3'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        segments, _ = whisper_model.transcribe(tmp_path, beam_size=5, language=None)
        os.remove(tmp_path)

        if not segments:
            raise ValueError("No speech detected")

        return ' '.join(s.text.strip() for s in segments if s.text.strip())
    except Exception as e:
        raise Exception(f"Audio processing failed: {str(e)}")

def extract_word_text(word_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            for chunk in word_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        with open(tmp_path, "rb") as docx_file:
            text = mammoth.extract_raw_text(docx_file).value
        os.remove(tmp_path)

        if not text.strip():
            raise ValueError("No text in Word document")
        return text
    except Exception as e:
        raise Exception(f"Word text extraction error: {str(e)}")

def extract_pdf_text(pdf_file):
    try:
        reader = PdfReader(pdf_file)
        text = '\n'.join(page.extract_text() for page in reader.pages if page.extract_text())
        if not text.strip():
            raise ValueError("No text in PDF")
        return text
    except Exception as e:
        raise Exception(f"PDF extraction error: {str(e)}")

def extract_ppt_text(ppt_file):
    try:
        prs = Presentation(ppt_file)
        text = '\n'.join(
            shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text")
        )
        if not text.strip():
            raise ValueError("No text in PowerPoint")
        return text
    except Exception as e:
        raise Exception(f"PowerPoint extraction error: {str(e)}")

def extract_excel_text(excel_file):
    try:
        wb = load_workbook(excel_file, read_only=True)
        text = '\n'.join(
            str(cell.value) for sheet in wb.worksheets for row in sheet.iter_rows()
            for cell in row if cell.value
        )
        if not text.strip():
            raise ValueError("No text in Excel")
        return text
    except Exception as e:
        raise Exception(f"Excel extraction error: {str(e)}")

def parse_questions(response_text, question_type='mcq'):
    questions = []
    topic = 'general'
    try:
        lines = response_text.strip().splitlines()
        for line in lines:
            if line.lower().startswith('topic:'):
                topic = line.split(':', 1)[1].strip()
                break

        blocks = response_text.strip().split("Q")[1:]

        for block in blocks:
            lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
            if not lines:
                continue

            question_text = lines[0].split(':', 1)[1].strip() if ':' in lines[0] else lines[0]
            answer_line = next((line for line in lines if line.lower().startswith(('answer:', 'ans:', 'a:'))), None)

            if question_type.lower() == 'mcq':
                options = [line[2:].strip() for line in lines[1:] if line.lower().startswith(('a.', 'b.', 'c.', 'd.'))]
                if len(options) == 4 and answer_line:
                    correct_index = ord(answer_line.split(':')[1].strip().upper()[0]) - ord('A')
                    if 0 <= correct_index < 4:
                        questions.append({
                            'question': question_text,
                            'options': options,
                            'answer': options[correct_index],
                            'topic': topic
                        })

            elif question_type.lower() == 'true_false' and answer_line:
                answer_text = answer_line.split(':')[1].strip().lower()
                correct_index = 0 if answer_text in ['true', 't', 'a'] else 1 if answer_text in ['false', 'f', 'b'] else -1
                if correct_index in [0, 1]:
                    questions.append({
                        'question': question_text,
                        'options': ['True', 'False'],
                        'answer': ['True', 'False'][correct_index],
                        'topic': topic
                    })
    except Exception as e:
        print(f"Error parsing questions: {str(e)}")

    return questions

class MultimodalQuizView(APIView):
    def get(self, request, pk):
        try:
            # Get user by pk
            user = User.objects.get(id=pk)
            return Response({
                'message': 'Please send a POST request with content to generate quiz',
                'supported_content_types': ['text', 'image', 'audio', 'video', 'pdf', 'word', 'ppt', 'excel', 'url'],
                'difficulty_levels': ['easy', 'medium', 'hard'],
                'question_types': ['mcq', 'true_false']
            })
        except user.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)

    def post(self, request, pk):
        try:
            token_key=request.data.get('token')
            if not token_key:
                return Response({'message':'Token is required'},status=status.HTTP_400_BAD_REQUEST)
            token = UserToken.objects.get(token=token_key, user=pk)
            if token.expires_at < datetime.utcnow():
                return Response({'error': 'Token has expired'}, status=status.HTTP_401_UNAUTHORIZED)

            user = token.user  # Already validated
            content_type = request.headers.get('Content-Type', '')
            is_multipart = 'multipart/form-data' in content_type.lower()
            
            # Parse input
            data = request.POST if is_multipart else request.data
            files = request.FILES if is_multipart else {}

            content_text = data.get('text', '').strip()
            url = data.get('url')
            difficulty = data.get('difficulty', 'medium')
            question_type = data.get('question_type', 'mcq')
            number_question = int(data.get('number_question', 10))

            # Validate inputs
            if not any([content_text, *files.values(), url]):
                return Response({'error': 'Provide at least one content input'}, status=status.HTTP_400_BAD_REQUEST)
            if difficulty not in ['easy', 'medium', 'hard']:
                return Response({'error': 'Invalid difficulty'}, status=status.HTTP_400_BAD_REQUEST)
            if question_type not in ['mcq', 'true_false']:
                return Response({'error': 'Invalid question type'}, status=status.HTTP_400_BAD_REQUEST)

            # Generate prompt
            difficulty_instruction = {
                'easy': 'Generate basic, straightforward questions suitable for beginners.',
                'medium': 'Generate moderately challenging questions that require good understanding.',
                'hard': 'Generate complex questions that require deep understanding and critical thinking.'
            }[difficulty]

            base_prompt = f"""
            You're an AI quiz generator.
            {difficulty_instruction}
            Based on the following content, first identify the main topic of the content.
            Then generate {number_question} {'questions with 4 options' if question_type == 'mcq' else 'true/false questions'} related to that topic.
            Format strictly like:
            Topic: <main_topic>
            
            Q: <question>
            A. <option>
            B. <option>
            C. <option>
            D. <option>
            Answer: <correct_option_letter>

            Text: {content_text}
            """ if question_type == 'mcq' else f"""
            You're an AI quiz generator.
            {difficulty_instruction}
            Based on the following content, first identify the main topic of the content.
            Then generate {number_question} true/false questions related to that topic.
            Format strictly like:
            Topic: <main_topic>
            
            Q: <question>
            A. True
            B. False
            Answer: <correct_option_letter>

            Text: {content_text}
            """

            parts = [{"text": base_prompt}]

            # Media extraction functions
            def update_text_and_parts(new_text, label):
                nonlocal content_text
                content_text = new_text
                parts[0]['text'] = parts[0]['text'].replace("Text: ", f"Text: {content_text}")
                parts.append({"text": f"Additional context from {label}: {new_text}"})

            for field, extractor, label in [
                ('audio', transcribe_audio, 'audio'),
                ('pdf', extract_pdf_text, 'PDF'),
                ('word', extract_word_text, 'Word document'),
                ('ppt', extract_ppt_text, 'PowerPoint'),
                ('excel', extract_excel_text, 'Excel'),
                ('url', extract_url_text, 'URL')
            ]:
                if data.get(field) or files.get(field):
                    try:
                        extracted = extractor(data.get(field) or files.get(field))
                        if not extracted:
                            return Response({'error': f'Could not extract from {label}'}, status=status.HTTP_400_BAD_REQUEST)
                        update_text_and_parts(extracted, label)
                    except Exception as e:
                        return Response({'error': f'Error processing {label}: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

            if image := files.get('image'):
                parts.append({
                    "inline_data": {
                        "mime_type": image.content_type,
                        "data": base64.b64encode(image.read()).decode()
                    }
                })

            if video := files.get('video'):
                frame_data, mime = extract_frame(video)
                parts.append({
                    "inline_data": {
                        "mime_type": mime,
                        "data": base64.b64encode(frame_data).decode()
                    }
                })

            # AI Generation
            model = genai.GenerativeModel("models/gemini-1.5-flash")
            response = model.generate_content(parts)
            output = response.text
            questions = parse_questions(output, question_type)

            if not questions:
                return Response({'message': 'Failed to generate questions'}, status=status.HTTP_400_BAD_REQUEST)

            main_topic = questions[0].get('topic', 'general')

            quiz_data = {
                'user': str(user.id),
                'title': f"Quiz on {main_topic}",
                'questions': questions,
                'number_question': len(questions),
                'difficulty': difficulty,
                'question_type': question_type,
                'content_type': [ct for ct in ['text', 'image', 'audio', 'video', 'pdf', 'word', 'ppt', 'excel', 'url'] if data.get(ct) or files.get(ct)],
                'topics': [main_topic],
            }

            quiz_serializer = QuizSerializer(data=quiz_data)
            if quiz_serializer.is_valid():
                quiz = quiz_serializer.save()
            else:
                return Response({'message': 'Invalid credentials'}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'message': 'Quiz generated successfully',
                'user_id': str(user.id),
                'quiz_id': str(quiz.id),
                'topics': main_topic,
                'questions': [
                    {
                        'question': q['question'],
                        'options': q['options'],
                        'answer': q['answer']
                    } for q in questions
                ]
            })

        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class SubmitQuizView(APIView):
    def post(self, request, pk):
        try:
            user = User.objects.get(id=pk)
            quiz_id = request.data.get('quiz_id')
            user_answers = request.data.get('user_answers')  # Dict of {question_id: selected_option_index}

            if not user or not quiz_id or not user_answers:
                return Response({'error': 'User ID, Quiz ID and user answers are required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                quiz = Quiz.objects.get(id=quiz_id)
            except DoesNotExist:
                return Response({'error': 'Quiz not found'}, status=status.HTTP_404_NOT_FOUND)

            score = 0
            correct_answers_count = 0
            total_questions = len(quiz.questions)

            evaluated_questions = []
            user_answer_texts = []

            for q_data in quiz.questions:
                question_id = str(q_data.get('_id'))
                correct_answer = q_data.get('answer')
                question_text = q_data.get('question')
                options = q_data.get('options', [])

                if question_id in user_answers:
                    selected_option_index = user_answers[question_id]
                    if 0 <= selected_option_index < len(options):
                        selected_answer = options[selected_option_index]
                        is_correct = selected_answer == correct_answer
                        if is_correct:
                            score += 1
                            correct_answers_count += 1
                        evaluated_questions.append({
                            'question_id': question_id,
                            'question': question_text,
                            'options': options,
                            'correct_answer': correct_answer,
                            'selected_answer': selected_answer,
                            'is_correct': is_correct
                        })
                        user_answer_texts.append(selected_answer)
                    else:
                        evaluated_questions.append({
                            'question_id': question_id,
                            'question': question_text,
                            'options': options,
                            'correct_answer': correct_answer,
                            'selected_answer': None,
                            'is_correct': False
                        })
                        user_answer_texts.append("")

            # Use QuizAttemptSerializer instead of direct create
            quiz_attempt_data = {
                'user': str(user.id),
                'quiz': str(quiz.id),
                'questions': evaluated_questions,
                'number_question': total_questions,
                'user_answers': user_answer_texts,
                'score': score,
                'difficulty': quiz.difficulty,
                'question_type': quiz.question_type,
                'topics': quiz.topics
            }

            serializer = QuizAttemptSerializer(data=quiz_attempt_data)
            if serializer.is_valid():
                attempt = serializer.save()
            else:
                return Response({'message':'invalid credantials'}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'message': 'Quiz submitted successfully',
                'score': score,
                'total_questions': total_questions,
                'correct_answers': correct_answers_count,
                'quiz_attempt_id': str(attempt.id)
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
