from django.db import models


class ActionType(models.Model):
    name = models.CharField(max_length=50, )
