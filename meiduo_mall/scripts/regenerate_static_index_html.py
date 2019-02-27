#! /usr/bin/env python
#指明执行哪个python执行代码
import os
import sys

#上级目录加到搜索包里
sys.path.insert(0, '../')

# 设置Django运行所依赖环境变量
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "meiduo_mall.settings.dev")

# 让Django进行一次初始化
import django
django.setup()

from contents.crons import generate_static_index_html

if __name__ == "__main__":
    # 生成静态首页index.html
    generate_static_index_html()