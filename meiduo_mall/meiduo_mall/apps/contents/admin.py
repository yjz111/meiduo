from django.contrib import admin
from  . import  models
# Register your models here.
#在广告内容contents应用中的admin.py中足注册模型类

admin.site.register(models.ContentCategory)
admin.site.register(models.Content)