from django.contrib import auth
from django.db import models

class User(auth.get_user_model()):
    class Meta:
        proxy = True
