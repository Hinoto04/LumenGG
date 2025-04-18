from django.db import models
from django.contrib.auth.models import User

# Create your models here.
def getUsername(self):
    return self.usernmae

User.add_to_class("__str__", getUsername)