from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('student-dashboard/', views.student_dashboard, name='student_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('recommend/', views.course_recommendation, name='course_recommendation'),
 
    path('courses/', views.courses_view, name='courses'),
    path('track_progress/', views.track_progress, name='track_progress'), 
    path('rewards/', views.rewards_view, name='rewards'),
    path('profile/', views.profile_view, name='profile'),

    path('your-course/', views.your_course, name='your_course'),

    # path('courses/java/', views.java_course, name='java_course'),
    # path('courses/python/', views.python_course, name='python_course'),
    # path('courses/cloud/', views.cloud_course, name='cloud_course'),
    # path('courses/data-science/', views.data_science_course, name='data_science_course'),
    # path('courses/web-application/', views.web_application_course, name='web_application_course'),

    path('course/<int:course_id>/', views.course_detail, name='course_detail'),
    path('enroll/<int:course_id>/', views.enroll_in_course, name='enroll_course'),

    path('java-beginner/', views.beginner_quiz_view, name='java_beginner_quiz'),
    path('java-intermediate/', views.intermediate_quiz_view, name='java_intermediate_quiz'),
    path('java-advanced/', views.advanced_quiz_view, name='java_advanced_quiz'), 


    path('python-beginner/', views.python_beginner_quiz_view, name='python_beginner_quiz'),
    path('python-intermediate/', views.python_intermediate_quiz_view, name='python_intermediate_quiz'),
    path('python-advanced/', views.python_advanced_quiz_view, name='python_advanced_quiz'),


    path('cloud-beginner/', views.cloud_computing_beginner_quiz_view, name='cloud_computing_beginner_quiz'),
    path('cloud-intermediate/', views.cloud_computing_intermediate_quiz_view, name='cloud_computing_intermediate_quiz'),
    path('cloud-advanced/', views.cloud_computing_advanced_quiz_view, name='cloud_computing_advanced_quiz'),


    path('data-science-beginner/', views.data_science_beginner_quiz_view, name='data_science_beginner_quiz'),
    path('data-science-intermediate/', views.data_science_intermediate_quiz_view, name='data_science_intermediate_quiz'),
    path('data-science-advanced/', views.data_science_advanced_quiz_view, name='data_science_advanced_quiz'),

    path('web_application-beginner/', views.web_development_beginner_quiz_view, name='web_development_beginner_quiz'),
    path('web_application-intermediate/', views.web_development_intermediate_quiz_view, name='web_development_intermediate_quiz'),
    path('web_application-advanced/', views.web_development_advanced_quiz_view, name='web_development_advanced_quiz'),

    path('rewards_and_quizzes/', views.rewards_and_quizzes, name='rewards_and_quizzes'),

    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),

    path('course_detail/<int:course_id>/', views.course_detail, name='course_detail'),  # Course Detail
    path('mark_quiz_attended/<int:quiz_id>/', views.mark_quiz_attended, name='mark_quiz_attended'),  # Mark Quiz as Attended
    path('update_course_progress/<int:course_id>/', views.update_course_progress, name='update_course_progress'),

    path('flexible-temp/', views.flexible_roadmap_placeholder, name='flexible_temp'), # Recommendations
     path('personalized-courses/', views.personalized_courses_view, name='personalized_courses'), #personalized_courses
    

]
