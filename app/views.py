from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import google.generativeai as genai
import base64
import tempfile
import os
import json
import razorpay
from django.conf import settings
from app.models import *
from mongoengine.errors import DoesNotExist, ValidationError
from datetime import datetime,timedelta
import cv2
# import whisper
# from pydub import AudioSegment
from faster_whisper import WhisperModel

genai.configure(api_key=settings.GEMINI_API_KEY)
whisper_model = WhisperModel("base", compute_type="float32")
# whisper_model = whisper.load_model("base")

# Helper functions remain unchanged
def extract_frame(video_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        tmp.write(video_file.read())
        tmp_path = tmp.name

    cap = cv2.VideoCapture(tmp_path)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    middle_frame = frame_count // 2
    cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)

    success, frame = cap.read()
    frame_path = tmp_path + "_frame.jpg"

    if success:
        cv2.imwrite(frame_path, frame)

    cap.release()
    os.remove(tmp_path)

    with open(frame_path, "rb") as f:
        image_data = f.read()

    os.remove(frame_path)
    return image_data, "image/jpeg"
def transcribe_audio(audio_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
        tmp.write(audio_file.read())
        tmp_path = tmp.name

    segments, info = whisper_model.transcribe(tmp_path, beam_size=5)
    text = " ".join([segment.text for segment in segments])

    os.remove(tmp_path)
    return text

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

            # For answer submission and database storage
            if request.data.get('submitted') or (is_multipart and request.POST.get('submitted')):
                user_answers = []
                if is_multipart:
                    user_answers = [request.POST.get(f'question_{i}') for i in range(len(questions))]
                else:
                    user_answers = request.data.get('user_answers', [])
                
                score = sum(1 for i, q in enumerate(questions) if user_answers[i] == q['answer'])
                
                # Create and save quiz attempt
                quiz_attempt = QuizAttempt(
                    user=request.user,
                    questions=questions,
                    user_answers=user_answers,
                    score=score,
                    total=len(questions),
                    difficulty=difficulty,
                    question_type=question_type
                )
                quiz_attempt.save()  # This triggers calculate_stats() method
                
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



# class UserDashboardView(APIView):
#     def get(self, request ,pk):
#        try:
#             # Get user details
#             user = User.objects.get(id=pk)
#             if not user:
#                 return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

#             # Get user's quiz attempts
#             quiz_attempts = QuizAttempt.objects(user=user).order_by('-created_at')
            
#             # Calculate statistics
#             total_attempts = quiz_attempts.count()
#             if total_attempts > 0:
#                 average_score = sum(attempt.score for attempt in quiz_attempts) / total_attempts
#                 best_score = max(attempt.score for attempt in quiz_attempts)
#                 recent_scores = [{
#                     'score': attempt.score,
#                     'total': attempt.total,
#                     'difficulty': attempt.difficulty,
#                     'date': attempt.created_at.strftime('%Y-%m-%d %H:%M:%S'),
#                     'type': attempt.question_type
#                 } for attempt in quiz_attempts[:5]]
#             else:
#                 average_score = 0
#                 best_score = 0
#                 recent_scores = []

#             # Prepare response data
#             dashboard_data = {
#                 'user_profile': {
#                     'full_name': user.full_name,
#                     'email': user.email,
#                     'phone_number': user.phone_number,
#                     'country_code': user.country_code,
#                     'profile_image': True if user.profile else False,
#                     'joined_date': user.created_at.strftime('%Y-%m-%d'),
#                     'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S')
#                 },
#                 'quiz_statistics': {
#                     'total_attempts': total_attempts,
#                     'average_score': round(average_score, 2),
#                     'best_score': best_score,
#                     'recent_scores': recent_scores
#                 },
#                 'activity_summary': {
#                     'mcq_attempts': QuizAttempt.objects(user=user, question_type='mcq').count(),
#                     'true_false_attempts': QuizAttempt.objects(user=user, question_type='true_false').count(),
#                     'by_difficulty': {
#                         'easy': QuizAttempt.objects(user=user, difficulty='easy').count(),
#                         'medium': QuizAttempt.objects(user=user, difficulty='medium').count(),
#                         'hard': QuizAttempt.objects(user=user, difficulty='hard').count()
#                     }
#                 }
#             }

#             return Response(dashboard_data, status=status.HTTP_200_OK)
#        except Exception as e:
#              return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
#     def put(self, request, pk):
#         try:
#             user = User.objects.get(id=pk)
#             if not user:
#                 return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

#             # Update user profile
#             data = request.data
#             if 'full_name' in data:
#                 user.full_name = data['full_name']
#             if 'phone_number' in data:
#                 user.phone_number = data['phone_number']
#             if 'country_code' in data:
#                 user.country_code = data['country_code']
#             if 'email' in data:
#                 user.email = data['email']
            
#             # Handle profile image update
#             profile_image = request.FILES.get('profile')
#             if profile_image:
#                 user.profile = profile_image

#             # Validate and save changes
#             user.clean()
#             user.save()

#             return Response({
#                 "message": "Profile updated successfully",
#                 "user": {
#                     "full_name": user.full_name,
#                     "email": user.email,
#                     "phone_number": user.phone_number,
#                     "country_code": user.country_code,
#                     "profile": True if user.profile else False
#                 }
#             }, status=status.HTTP_200_OK)

#         except ValueError as e:
#             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
class UserDashboardView(APIView):
    def get(self, request, pk):
        try:
            # Get user details
            user = User.objects.get(id=pk)
            if not user:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            # Get user's quiz attempts
            quiz_attempts = QuizAttempt.objects(user=user).order_by('-created_at')
            
            # Get streak information
            streak = UserStreak.objects(user=user).first()
            
            # Get points information
            points = UserPoints.objects(user=user).first()
            
            # Get subscription details
            subscription = Subscription.objects(user=user, is_active=True).first()
            
            # Get saved quizzes
            saved_quizzes = SavedQuiz.objects(user=user).order_by('-saved_at')
            
            # Get payment history
            payments = Payment.objects(user=user).order_by('-payment_date')
            
            # Get feedback history
            feedback = Feedback.objects(user=user).order_by('-created_at')
            
            # Calculate statistics and learning curve
            total_attempts = quiz_attempts.count()
            if total_attempts > 0:
                # Calculate average scores over time for learning curve
                learning_curve = [{
                    'date': attempt.created_at.strftime('%Y-%m-%d'),
                    'score': attempt.score,
                    'accuracy': attempt.accuracy,
                    'moving_avg': sum(qa.accuracy for qa in quiz_attempts[max(0, i-4):i+1])/min(5, i+1)
                } for i, attempt in enumerate(quiz_attempts)]
                
                # Calculate overall statistics
                average_score = sum(attempt.score for attempt in quiz_attempts) / total_attempts
                best_score = max(attempt.score for attempt in quiz_attempts)
                
                # Get recent scores with detailed stats
                recent_scores = [{
                    'score': attempt.score,
                    'total': attempt.total,
                    'difficulty': attempt.difficulty,
                    'date': attempt.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'type': attempt.question_type,
                    'accuracy': attempt.accuracy,
                    'points_earned': attempt.points_earned,
                    'topics': attempt.topics,
                    'weak_topics': attempt.weak_topics,
                    'rank': attempt.rank,
                    'percentile': attempt.percentile,
                    'review_notes': attempt.review_notes
                } for attempt in quiz_attempts[:10]]
                
                # Identify overall weak topics
                topic_accuracies = {}
                for attempt in quiz_attempts:
                    for topic in attempt.topics:
                        if topic not in topic_accuracies:
                            topic_accuracies[topic] = {'total': 0, 'correct': 0}
                        topic_accuracies[topic]['total'] += 1
                        if topic not in attempt.weak_topics:
                            topic_accuracies[topic]['correct'] += 1
                
                weak_topics = [
                    {'topic': topic, 'accuracy': (stats['correct']/stats['total']*100)}
                    for topic, stats in topic_accuracies.items()
                    if (stats['correct']/stats['total']*100) < 60
                ]
            else:
                learning_curve = []
                average_score = 0
                best_score = 0
                recent_scores = []
                weak_topics = []

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
                'streak_info': {
                    'current_streak': streak.current_streak if streak else 0,
                    'longest_streak': streak.longest_streak if streak else 0,
                    'last_quiz_date': streak.last_quiz_date.strftime('%Y-%m-%d') if streak and streak.last_quiz_date else None,
                    'streak_history': streak.streak_history if streak else []
                },
                'points_info': {
                    'total_points': points.total_points if points else 0,
                    'level': points.level if points else 1,
                    'points_history': points.points_history if points else []
                },
                'subscription_info': {
                    'plan_name': subscription.plan_name if subscription else 'Free',
                    'credits': subscription.credits if subscription else 0,
                    'valid_until': subscription.end_date.strftime('%Y-%m-%d') if subscription else None,
                    'is_active': subscription.is_active if subscription else False
                },
                'quiz_statistics': {
                    'total_attempts': total_attempts,
                    'average_score': round(average_score, 2),
                    'best_score': best_score,
                    'recent_scores': recent_scores,
                    'learning_curve': learning_curve,
                    'weak_topics': weak_topics
                },
                'saved_quizzes': [{
                    'quiz_id': str(sq.quiz_attempt.id),
                    'saved_at': sq.saved_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'notes': sq.notes,
                    'score': sq.quiz_attempt.score,
                    'total': sq.quiz_attempt.total,
                    'topics': sq.quiz_attempt.topics
                } for sq in saved_quizzes],
                'payment_history': [{
                    'transaction_id': payment.transaction_id,
                    'amount': payment.amount,
                    'date': payment.payment_date.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': payment.status,
                    'plan_name': payment.subscription.plan_name if payment.subscription else None,
                    'invoice_url': payment.invoice_url
                } for payment in payments],
                'feedback_history': [{
                    'type': f.type,
                    'title': f.title,
                    'description': f.description,
                    'status': f.status,
                    'created_at': f.created_at.strftime('%Y-%m-%d %H:%M:%S')
                } for f in feedback],
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

    def post(self, request, pk):
        try:
            user = User.objects.get(id=pk)
            if not user:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

            action = request.data.get('action')
            if action == 'create_payment':
                amount = request.data.get('amount')
                if not amount:
                    return Response({'error': 'Amount is required'}, status=status.HTTP_400_BAD_REQUEST)

                # Initialize Razorpay client
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

                # Create Razorpay order
                order_data = {
                    'amount': int(float(amount) * 100),  # Convert to paise
                    'currency': 'INR',
                    'receipt': f'order_{pk}_{datetime.now().timestamp()}',
                    'payment_capture': 1
                }
                order = client.order.create(data=order_data)

                # Create Payment record
                payment = Payment(
                    user=user,
                    amount=float(amount),
                    transaction_id=order['id'],
                    status='pending'
                ).save()

                return Response({
                    'order_id': order['id'],
                    'amount': amount,
                    'key_id': settings.RAZORPAY_KEY_ID
                })

            elif action == 'verify_payment':
                payment_id = request.data.get('razorpay_payment_id')
                order_id = request.data.get('razorpay_order_id')
                signature = request.data.get('razorpay_signature')

                # Verify signature
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                try:
                    client.utility.verify_payment_signature({
                        'razorpay_payment_id': payment_id,
                        'razorpay_order_id': order_id,
                        'razorpay_signature': signature
                    })
                except:
                    return Response({'error': 'Invalid payment signature'}, 
                                  status=status.HTTP_400_BAD_REQUEST)

                # Update payment status
                payment = Payment.objects.get(transaction_id=order_id)
                payment.status = 'completed'
                payment.save()

                # If this is a subscription payment, activate the subscription
                if 'plan_name' in request.data:
                    subscription = Subscription(
                        user=user,
                        plan_name=request.data['plan_name'],
                        credits=request.data.get('credits', 0),
                        end_date=datetime.now() + timedelta(days=30),  # Adjust based on plan
                        is_active=True
                    ).save()
                    payment.subscription = subscription
                    payment.save()

                return Response({'status': 'Payment successful'})

            elif action == 'save_quiz':
                quiz_id = request.data.get('quiz_id')
                notes = request.data.get('notes')
                
                quiz_attempt = QuizAttempt.objects.get(id=quiz_id)
                SavedQuiz(user=user, quiz_attempt=quiz_attempt, notes=notes).save()
                return Response({'status': 'Quiz saved successfully'})

            elif action == 'submit_feedback':
                feedback_type = request.data.get('type')
                title = request.data.get('title')
                description = request.data.get('description')
                
                Feedback(
                    user=user,
                    type=feedback_type,
                    title=title,
                    description=description
                ).save()
                return Response({'status': 'Feedback submitted successfully'})

            else:
                return Response({'error': 'Invalid action'}, 
                              status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)