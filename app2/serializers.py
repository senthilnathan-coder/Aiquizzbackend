from rest_framework_mongoengine.serializers import DocumentSerializer
from app2.models import *
from app.models import *

class AdminSerializer(DocumentSerializer):
    class Meta:
        model= Admin
        fields=['id','fullname','email','role']
        read_fields=['is_active','created_at','last_login']


class UserManagementSerializer(DocumentSerializer):
    class Meta:
        model=User
        fields=['id','full_name','email','phone_number','country_code','is_active']
        read_fields=['created_at','last_login']