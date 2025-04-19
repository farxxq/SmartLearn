from django.db import models
from django.contrib.auth.models import User


# Updated StudentProfile to include student-specific details
class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    is_active = models.BooleanField(default=True)
    
# Course model
class Course(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField()
    topic = models.CharField(max_length=255)
    prerequisite = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='required_courses')


# UserCourse model that tracks user-course relationship
class UserCourse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    progress = models.IntegerField(default=0)  # Use IntegerField not default=0.0 for integer
    rewards_earned = models.IntegerField(default=0)
    class Meta:
        # This prevents enrolling in the SAME course twice
        unique_together = ('user', 'course')


# Quiz model
class Quiz(models.Model):
    name = models.CharField(max_length=255)
    level = models.CharField(max_length=50)
    mark = models.IntegerField(default=0)
    date_created = models.DateTimeField(auto_now_add=True)
    attendees = models.ManyToManyField(User, related_name='attended_quizzes', blank=True)

# UserProgress model
class UserProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_course = models.ForeignKey(UserCourse, on_delete=models.CASCADE)  # renamed field for clarity
    beginner_progress = models.IntegerField(default=0)
    intermediate_progress = models.IntegerField(default=0)
    advanced_progress = models.IntegerField(default=0)

    @property
    def total_progress(self):
        progress = 0
        if self.beginner_progress >= 60: 
            progress += 30
        if self.intermediate_progress >= 60:
            progress += 30
        if self.advanced_progress >= 60:
            progress += 40
        return progress

    @property
    def stars(self):
        stars = 0
        if self.beginner_progress >= 60:
            stars += 1
        if self.intermediate_progress >= 60:
            stars += 2
        if self.advanced_progress >= 60:
            stars += 3
        return stars


# Reward model
class Reward(models.Model):
    LEVEL_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date_earned = models.DateField(auto_now_add=True)

    def star_count(self):
        return {
            'Beginner': 1,
            'Intermediate': 2,
            'Advanced': 3
        }.get(self.level, 0)


# Topic model
class Topic(models.Model):
    name = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='topics')
    is_completed = models.BooleanField(default=False)
