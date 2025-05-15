from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
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
from app.models import *
from mongoengine.errors import DoesNotExist, ValidationError
from datetime import datetime

genai.configure(api_key=settings.GEMINI_API_KEY)
whistle_model = whisper.load_model("base")

# Helper functions remain unchanged
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

def parse_questions(response_text, question_type='mcq'):
    questions = []
    blocks = response_text.strip().split("Q")[1:]
    
    try:
        for block in blocks:
            try:
                lines = [line.strip() for line in block.strip().splitlines() if line.strip()]
                
                if not lines:
                    continue
                    
                # Extract question text more flexibly
                question_text = lines[0]
                if ':' in question_text:
                    question_text = question_text.split(':', 1)[1].strip()
                
                # Handle MCQ format
                if question_type == 'mcq':
                    options = []
                    answer_line = None
                    
                    # Extract options and answer more flexibly
                    for line in lines[1:]:
                        line = line.strip()
                        if line.lower().startswith(('a.', 'b.', 'c.', 'd.')):
                            options.append(line[2:].strip())
                        elif any(line.lower().startswith(prefix) for prefix in ['answer:', 'ans:', 'a:']):
                            answer_line = line
                    
                    if len(options) == 4 and answer_line:
                        correct_letter = answer_line.split(':')[1].strip().upper()[0]
                        correct_index = ord(correct_letter) - ord('A')
                        
                        if 0 <= correct_index < len(options):
                            questions.append({
                                'question': question_text,
                                'options': options,
                                'answer': options[correct_index]
                            })
                
                # Handle True/False format
                else:
                    options = ['True', 'False']
                    answer_line = None
                    
                    # Find answer line with flexible matching
                    for line in lines:
                        if any(line.lower().startswith(prefix) for prefix in ['answer:', 'ans:', 'a:']):
                            answer_line = line
                            break
                    
                    if answer_line:
                        answer_text = answer_line.split(':')[1].strip().upper()
                        correct_index = None
                        
                        # Handle multiple answer formats
                        if answer_text in ['A', 'TRUE', 'T']:
                            correct_index = 0
                        elif answer_text in ['B', 'FALSE', 'F']:
                            correct_index = 1
                        elif answer_text[0] in ['A', 'B']:
                            correct_index = ord(answer_text[0]) - ord('A')
                        
                        if correct_index is not None and 0 <= correct_index < len(options):
                            questions.append({
                                'question': question_text,
                                'options': options,
                                'answer': options[correct_index]
                            })
            except Exception as block_error:
                print(f"Error parsing block: {str(block_error)}")
                continue
                
    except Exception as e:
        print(f"Error parsing questions: {str(e)}")
    
    return questions

class MultimodalQuizView(APIView):
    def get(self, request):
        return Response({
            'message': 'Please send a POST request with content to generate quiz',
            'supported_content_types': ['text', 'image', 'audio', 'video'],
            'difficulty_levels': ['easy', 'medium', 'hard'],
            'question_types': ['mcq', 'true_false']
        })

    def post(self, request):
        try:
            # Handle multipart form data or JSON
            content_type = request.headers.get('Content-Type', '')
            is_multipart = 'multipart/form-data' in content_type.lower()

            if is_multipart:
                content_text = request.POST.get('content', '')
                image = request.FILES.get('image')
                audio = request.FILES.get('audio')
                video = request.FILES.get('video')
                difficulty = request.POST.get('difficulty', 'medium')
                question_type = request.POST.get('question_type', 'mcq')
            else:
                content_text = request.data.get('content', '')
                image = None
                audio = None
                video = None
                difficulty = request.data.get('difficulty', 'medium')
                question_type = request.data.get('question_type', 'mcq')

            if not any([content_text.strip(), image, audio, video]):
                return Response({
                    'error': 'Please provide at least one type of content (text/image/audio/video)'
                }, status=status.HTTP_400_BAD_REQUEST)

            if difficulty not in ['easy', 'medium', 'hard']:
                return Response({
                    'error': 'Invalid difficulty level. Choose from: easy, medium, hard'
                }, status=status.HTTP_400_BAD_REQUEST)

            if question_type not in ['mcq', 'true_false']:
                return Response({
                    'error': 'Invalid question type. Choose from: mcq, true_false'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Generate quiz prompt based on difficulty and question type
            difficulty_instructions = {
                'easy': 'Generate basic, straightforward questions suitable for beginners.',
                'medium': 'Generate moderately challenging questions that require good understanding.',
                'hard': 'Generate complex questions that require deep understanding and critical thinking.'
            }

            if question_type == 'mcq':
                prompt = f"""
                You're an AI quiz generator.
                {difficulty_instructions[difficulty]}
                Based on the following content, generate 10 multiple choice questions with 4 options.
                Format strictly like:
                Q: <question>
                A. <option>
                B. <option>
                C. <option>
                D. <option>
                Answer: <correct_option_letter>

                Text: {content_text}
                """
            else:  # true_false
                prompt = f"""
                You're an AI quiz generator.
                {difficulty_instructions[difficulty]}
                Based on the following content, generate 10 true/false questions.
                Format strictly like:
                Q: <question>
                A. True
                B. False
                Answer: <correct_option_letter>

                Text: {content_text}
                """

            parts = [{"text": prompt}]

            # Process multimedia content
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

            # Generate questions
            model = genai.GenerativeModel("models/gemini-1.5-flash")
            response = model.generate_content(parts)
            output = response.text
            questions = parse_questions(output, question_type)

            if not questions:
                return Response({
                    'error': 'Failed to generate questions'
                }, status=status.HTTP_400_BAD_REQUEST)

            # For answer submission
            if is_multipart and request.POST.get('submitted'):
                user_answers = [request.POST.get(f'question_{i}') for i in range(len(questions))]
                score = sum(1 for i, q in enumerate(questions) if user_answers[i] == q['answer'])
                
                return Response({
                    'questions': questions,
                    'user_answers': user_answers,
                    'score': score,
                    'total': len(questions),
                    'difficulty': difficulty,
                    'question_type': question_type
                })

            return Response({
                'success': True,
                'questions': questions,
                'difficulty': difficulty,
                'question_type': question_type
            })

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SignupView(APIView):
    def post(self, request):
        try:
            # Extract user data
            data = request.data
            full_name = data.get('full_name')
            phone_number = data.get('phone_number')
            country_code = data.get('country_code')
            email = data.get('email')
            password = data.get('password')
            confirm_password = data.get('confirm_password')
            profile_image = request.FILES.get('profile')

            # Check if required fields are present
            if not all([full_name, phone_number, country_code, email, password, confirm_password, profile_image]):
                return Response({'error': 'All fields including profile image are required'}, status=status.HTTP_400_BAD_REQUEST)

            # Check if user already exists
            if User.objects(email=email).first():
                return Response({'error': 'useremail already registered'}, status=status.HTTP_400_BAD_REQUEST)
            
            if User.objects(phone_number=phone_number).first():
                return Response({'error': 'Phone number already registered'}, status=status.HTTP_400_BAD_REQUEST)

            # Create new user
            user = User(
                full_name=full_name,
                phone_number=phone_number,
                country_code=country_code,
                email=email,
                profile=profile_image
            )

            try:
                user.set_password(password, confirm_password)
                user.clean()
                user.save()
                
                return Response({
                    'message': 'User registered successfully',
                    'user': {
                        'full_name': user.full_name,
                        'email': user.email,
                        'phone_number': user.phone_number,
                        'country_code': user.country_code,
                        'profile': True
                    }
                }, status=status.HTTP_201_CREATED)

            except ValueError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SigninView(APIView):
    def post(self, request):
        try:
            data = request.data
            email = data.get('email')
            password = data.get('password')

            if not all([email, password]):
                return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

            user = User.objects(email=email).first()
            if not user or not user.check_password(password):
                return Response({'error': 'Invalid email or password'}, status=status.HTTP_401_UNAUTHORIZED)

            if not user.is_active:
                return Response({'error': 'Account is disabled'}, status=status.HTTP_403_FORBIDDEN)

            # Update last login
            user.last_login = datetime.utcnow()
            user.save()

            return Response({
                'message': 'Login successful',
                'user': {
                    'full_name': user.full_name,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'country_code': user.country_code,
                    'profile': True
                }
            })

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserDetailView(APIView):
    def get(self, request, pk):
        try:
            user = User.objects.get(id=pk)
            user_data = {
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "country_code": user.country_code,
                "email": user.email,
                "is_active": user.is_active
            }
            return Response({"user": user_data})
        
        except (DoesNotExist, ValidationError):
            return Response({"error": "User not found or invalid ID"}, status=status.HTTP_404_NOT_FOUND)



class UserDashboardView(APIView):
    def get(self, request ,pk):
       try:
            # Get user details
            user = User.objects.get(id=pk)
            if not user:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Get user's quiz attempts
            quiz_attempts = QuizAttempt.objects(user=user).order_by('-created_at')
            
            # Calculate statistics
            total_attempts = quiz_attempts.count()
            if total_attempts > 0:
                average_score = sum(attempt.score for attempt in quiz_attempts) / total_attempts
                best_score = max(attempt.score for attempt in quiz_attempts)
                recent_scores = [{
                    'score': attempt.score,
                    'total': attempt.total,
                    'difficulty': attempt.difficulty,
                    'date': attempt.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': attempt.question_type
                } for attempt in quiz_attempts[:5]]
            else:
                average_score = 0
                best_score = 0
                recent_scores = []

            # Prepare response data
            dashboard_data = {
                'user_profile': {
                    'full_name': user.full_name,
                    'email': user.email,
                    'phone_number': user.phone_number,
                    'country_code': user.country_code,
                    'profile_image': True if user.profile else False,
                    'joined_date': user.created_at.strftime('%Y-%m-%d'),
                    'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S')
                },
                'quiz_statistics': {
                    'total_attempts': total_attempts,
                    'average_score': round(average_score, 2),
                    'best_score': best_score,
                    'recent_scores': recent_scores
                },
                'activity_summary': {
                    'mcq_attempts': QuizAttempt.objects(user=user, question_type='mcq').count(),
                    'true_false_attempts': QuizAttempt.objects(user=user, question_type='true_false').count(),
                    'by_difficulty': {
                        'easy': QuizAttempt.objects(user=user, difficulty='easy').count(),
                        'medium': QuizAttempt.objects(user=user, difficulty='medium').count(),
                        'hard': QuizAttempt.objects(user=user, difficulty='hard').count()
                    }
                }
            }

            return Response(dashboard_data, status=status.HTTP_200_OK)
       except Exception as e:
             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if not user:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Update user profile
            data = request.data
            if 'full_name' in data:
                user.full_name = data['full_name']
            if 'phone_number' in data:
                user.phone_number = data['phone_number']
            if 'country_code' in data:
                user.country_code = data['country_code']
            if 'email' in data:
                user.email = data['email']
            
            # Handle profile image update
            profile_image = request.FILES.get('profile')
            if profile_image:
                user.profile = profile_image

            # Validate and save changes
            user.clean()
            user.save()

            return Response({
                "message": "Profile updated successfully",
                "user": {
                    "full_name": user.full_name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "country_code": user.country_code,
                    "profile": True if user.profile else False
                }
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)