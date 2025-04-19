from django.contrib import admin
from .models import (
    StudentProfile,
    Course,
    UserCourse,
    Quiz,
    UserProgress,
    Reward,
    Topic
)

admin.site.register(StudentProfile)
admin.site.register(Course)
admin.site.register(UserCourse)
admin.site.register(Quiz)
admin.site.register(UserProgress)
admin.site.register(Reward)
admin.site.register(Topic)
