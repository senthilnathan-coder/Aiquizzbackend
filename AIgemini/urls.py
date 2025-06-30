"""
URL configuration for AIgemini project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from rest_framework.response import Response
from rest_framework.views import APIView
class Apicheck(APIView):
    def get(self,request):
        return Response({'message':'API is running succussfully'})


urlpatterns = [
    # path('admin/', admin.site.urls),
    path('',Apicheck.as_view(),name='api_check'),
    path('app/',include('app.urls')),
    path('app2/',include('app2.urls')),
    path('app3/',include('app3.urls')),
    path('payments/',include('payments.urls')),
    path('api',include('flashcard.urls'))
]
