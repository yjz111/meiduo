# -*- coding: utf-8 -*-
# Generated by Django 1.11.11 on 2018-08-07 06:04
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Picture',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='pics', verbose_name='图片')),
            ],
            options={
                'verbose_name': '图片上传测试',
                'db_table': 'tb_pics',
                'verbose_name_plural': '图片上传测试',
            },
        ),
    ]
