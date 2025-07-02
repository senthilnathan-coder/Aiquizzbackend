from django.shortcuts import render
# Create your views here.
from rest_framework.views import APIView
import google.generativeai as genai
from rest_framework.response import Response
from app2.models import AuthToken
from payments.models import UserSubscription
from rest_framework import status
from datetime import datetime

class FlashcardView(APIView):
    def post(self, request, pk):
        token_key = request.data.get('token')
        topic = request.data.get('topic', '').strip()
        language=request.data.get('language','en')
        number_flashcard=int(request.data.get('number_flashcard',10))

        if not token_key or not topic:
            return Response({'error': 'Token and topic are required'}, status=400)
        if not (1 <= number_flashcard <=25):
            return Response({'error': 'number_flashcard must be between 1 and 25'}, status=400)

        try:
            token = AuthToken.objects.only('token', 'user', 'expires_at').get(token=token_key, user=pk)
            if token.expires_at < datetime.utcnow():
                return Response({'error': 'Token expired'}, status=401)

            user = token.user
            if user.role != 'user':
                return Response({'error': 'Access denied: not a user'}, status=403)
            
            subscription = UserSubscription.objects(user=user.id, is_active=True).order_by('-start_date').first()
            if not subscription:
                return Response({'error': 'No active subscription found'}, status=403)
            if subscription.end_date and subscription.end_date < datetime.utcnow():
                subscription.is_active = False
                subscription.save()
                return Response({'error': 'Subscription expired'}, status=403)
            if subscription.remaining_credits <= 0:
                return Response({'error': 'No remaining credits'}, status=403)
            language_map = {
                'en': 'English', 'ta': 'தமிழ்', 'hi': 'हिन्दी', 'za': 'Afrikaans', 'de': 'Deutsch',
                'es': 'Español', 'ph': 'Filipino', 'fr': 'Français', 'it': 'Italiano', 'tr': 'Turkish',
                'ru': 'Русский', 'ae': 'العربية', 'jp': '日本語', 'kr': '한국어', 'ms': 'Malay'
            }
            lang_name = language_map.get(language, language.lower())

            prompt = (
                f"Generate exactly {number_flashcard} flashcards for the topic \"{topic}\". "
                f"Each should be in the format: Term: Definition. One per line.\n"
                f"Ensure terms and definitions are distinct and clearly separated by a single colon.\n"
                f"Example:\nWater: A colorless, transparent, odorless liquid\nOxygen: A gas essential for respiration\n"
                f"Language of flashcards must be strictly {lang_name}."
            )
            if subscription.plan.name.upper() != 'TRIAL':
                model = genai.GenerativeModel("models/gemini-2.5-flash")
                result = model.generate_content(prompt)

                flashcards = []
                lines = result.text.strip().split("\n")
                for line in lines:
                    if ":" in line:
                        term, definition = map(str.strip, line.split(":", 1))
                        if term and definition:
                            flashcards.append({'term': term, 'definition': definition})

                if not flashcards:
                    return Response({'error': 'No valid flashcards generated'}, status=400)

                flashcards = flashcards[:number_flashcard]

                subscription.remaining_credits -= 1
                subscription.save()

                return Response({
                    'message': 'Flashcards generated',
                    'topic': topic,
                    'flashcards': flashcards,
                    'remaining_credits': subscription.remaining_credits
                })
            else:
                return Response({'error': 'Flashcard generation is not available for TRIAL plan'}, status=400)
          

        except Exception as e:
            return Response({'error': str(e)}, status=500)