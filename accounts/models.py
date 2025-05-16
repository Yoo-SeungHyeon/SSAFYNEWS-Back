from django.db import models
from django.contrib.auth.models import AbstractUser

# 기본 User 모델을 확장하기 위해 AbstractUser를 상속받습니다.
class User(AbstractUser):
    pass
