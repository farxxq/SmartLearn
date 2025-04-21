from django.shortcuts import render, redirect, get_object_or_404
import json
from django.http import JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, LoginForm
from .models import StudentProfile
from django.urls import path
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import admin
from .models import UserCourse
from django.shortcuts import render, redirect
from django.urls import reverse
import joblib
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from .models import Reward
from django.contrib.auth.models import User
from .models import Course, UserCourse, Reward, Quiz, Topic, Course, StudentProfile, UserProgress
from django.db.models import Avg
import math
from django.conf import settings
import google.generativeai as genai

# Configure Gemini (consider doing this once globally if preferred)
try:
    if settings.GEMINI_API_KEY:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model_gemini = genai.GenerativeModel("gemini-1.5-flash") # Or your preferred model
    else:
        model_gemini = None
        print("Warning: GEMINI_API_KEY not found in settings.")
except AttributeError:
    model_gemini = None
    print("Warning: GEMINI_API_KEY setting missing.")
except Exception as e:
    model_gemini = None
    print(f"Error configuring Gemini: {e}")

def generate_roadmap_prompt(course_name, user_profile=None, user_prefs=None, existing_topics=None): # Added user_prefs
    prompt = f"""Generate content for a new online course titled "{course_name}".

Provide the following information in sections clearly marked with triple hashes (###):

### Course Description ###
A concise, engaging one-paragraph description suitable for a course catalog.

### Topic List ###
A comma-separated list of 5-10 key topic names that form a logical learning path for this course, starting with fundamentals. Example: Topic 1, Topic 2, Another Topic Name

### Detailed Roadmap ###
A step-by-step learning roadmap expanding on the topics above. Structure as a numbered list. Each item should be a topic name followed by a brief one-sentence description.

"""

    # --- Add specific user preferences context if available ---
    if user_prefs: # Check if the dictionary exists and is not empty
        prompt += f"""Tailor the roadmap for a learner with the following profile:
- Age: {user_prefs.get('age', 'N/A')}
- Degree: {user_prefs.get('degree', 'N/A')}
- GPA: {user_prefs.get('gpa', 'N/A')}
- Learning Module Preference: {user_prefs.get('module_preference', 'N/A')}
- Time Available Daily (hrs): {user_prefs.get('time_available_hrs', 'N/A')}

Adjust the pace, depth, or examples in the roadmap based on this profile if possible.

"""
    elif user_profile and hasattr(user_profile, 'user'): # Fallback to basic profile if prefs not found
        prompt += f"""Consider the learner:
- Username: {user_profile.user.username}
- Name: {user_profile.name if hasattr(user_profile, 'name') and user_profile.name else 'N/A'}

"""
    # --- End user context ---

    if existing_topics:
        topic_names = ", ".join([t.name for t in existing_topics])
        prompt += f"The course already includes these topics (you can incorporate or expand on them): {topic_names}.\n\n"

    prompt += "Ensure the output strictly follows the requested format with the ### markers and focuses on the course content."

    return prompt

def parse_ai_response(response_text):
    """
    Parses the AI response text based on predefined markers.
    Returns a dictionary with 'description', 'topic_list', and 'roadmap_text'.
    """
    data = {
        'description': None,
        'topic_list': [],
        'roadmap_text': None
    }
    if not response_text: # Handle empty input
        return data

    try:
        # Use partition for robustness - finds first occurrence
        _, marker1, after_desc_marker = response_text.partition('### Course Description ###')
        if marker1:
            desc_part, marker2, after_topics_marker = after_desc_marker.partition('### Topic List ###')
            data['description'] = desc_part.strip()
            if marker2:
                topics_part, marker3, after_roadmap_marker = after_topics_marker.partition('### Detailed Roadmap ###')
                topic_str = topics_part.strip()
                # Split topics, strip whitespace, filter empty strings
                data['topic_list'] = [topic.strip() for topic in topic_str.split(',') if topic.strip()]
                if marker3:
                    data['roadmap_text'] = after_roadmap_marker.strip()
                # If roadmap marker not found, maybe topics was the last section
                elif not data['roadmap_text'] and not marker3:
                     data['roadmap_text'] = "Roadmap section not found in AI response."

            # If topic list marker not found, maybe description was last
            elif not marker2 and not data['topic_list']:
                 data['roadmap_text'] = "Topic list and Roadmap sections not found in AI response."


    except Exception as e:
        print(f"Error parsing AI response: {e}")
        # Fallback: Return the full text as roadmap if parsing fails badly
        if not data['roadmap_text'] and response_text:
             data['roadmap_text'] = f"Could not parse AI response. Raw:\n{response_text.strip()}"
        elif not data['roadmap_text']:
             data['roadmap_text'] = "Could not parse empty or invalid AI response."

    return data


# Display all students and their associated courses and progress
def student_dashboard(request, user_id):
    # user = get_object_or_404(User, id=user_id)
    user = request.user
    student_profile = StudentProfile.objects.get(user=user)
    user_courses = UserCourse.objects.filter(user=user)
    quizzes = Quiz.objects.filter(attendees=user)
    rewards = Reward.objects.filter(user=user)

    completed_course_id = request.GET.get('completed')
    completed_course_info = None
    if completed_course_id:
        try:
            # Fetch course details to show the name
            completed_course = Course.objects.get(id=completed_course_id)
            # Make sure the current user is actually enrolled and completed it (optional check)
            if UserCourse.objects.filter(user=request.user, course=completed_course, progress=100).exists():
                 completed_course_info = {
                     'id': completed_course.id,
                     'name': completed_course.name
                 }
        except Course.DoesNotExist:
            pass # Ignore if ID is invalid
    
    enrolled_user_courses = UserCourse.objects.filter(user=request.user).select_related('course')
    enrolled_course_ids = [uc.course.id for uc in enrolled_user_courses]
    available_courses = Course.objects.exclude(id__in=enrolled_course_ids)


    context = {
        'student_profile': student_profile,
        'user_courses': user_courses,
        'quizzes': quizzes,
        'rewards': rewards,
        'enrolled_courses': enrolled_user_courses, 
        'available_courses': available_courses,
        'completed_course_info': completed_course_info, # Pass info to template
    }
    return render(request, 'student_dashboard.html', context)

# Display a specific course and the user's progress on it
def course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    topics = Topic.objects.filter(course=course)
    user_course = UserCourse.objects.filter(course=course)

    is_enrolled = False # Default to not enrolled
    if request.user.is_authenticated: # Make sure user is logged in
        is_enrolled = UserCourse.objects.filter(user=request.user, course=course).exists()

    context = {
        'course': course,
        'topics': topics,
        'is_enrolled': is_enrolled,
    }
    return render(request, 'course_detail.html', context)
    # return render(request, 'test_course_detail_find.html', context)

# Mark quiz as attended and track progress
def mark_quiz_attended(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    quiz.attended = True
    quiz.save()
    return HttpResponse("Quiz marked as attended!")

# Update course progress
def update_course_progress(request, user_id, course_id):
    user = get_object_or_404(User, id=user_id)
    course = get_object_or_404(Course, id=course_id)
    user_course = UserCourse.objects.get(user=user, course=course)

    # Update progress, in this case we simulate it with a fixed value
    user_course.progress = 100  # For example, we set progress to 100
    user_course.save()

    return HttpResponse(f"Course progress updated for {course.name}.")


@login_required
def profile_view(request):
    user = request.user
    user_courses = UserCourse.objects.filter(user=user)

    try:
        user_progress = UserProgress.objects.get(user=user)
        total_progress = int(user_progress.total_progress)
        total_stars = int(user_progress.stars)
    except UserProgress.DoesNotExist:
        total_progress = 0
        total_stars = 0

    # Set stars based on total progress level
    if total_progress >= 80:
        total_stars = 3  # Advanced level
    elif total_progress >= 50:
        total_stars = 2  # Intermediate level
    elif total_progress >= 20:
        total_stars = 1  # Beginner level
    else:
        total_stars = 0  # No stars earned yet

    return render(request, 'accounts/profile.html', {
        'user_courses': user_courses,
        'total_progress': total_progress,
        'total_stars': total_stars,  # Pass the updated stars to the template
    })

    
@login_required
def rewards_view(request):
    rewards = Reward.objects.filter(user=request.user)
    return render(request, 'rewards.html', {'rewards': rewards})

@login_required
def track_progress(request):
    user = request.user
    user_course = UserCourse.objects.filter(user=user).first()  # Get the UserCourse instance

    # If there is no user_course, you may want to handle it gracefully.
    if not user_course:
        return render(request, 'accounts/track_progress.html', {'message': 'You are not enrolled in any course.'})

    # Beginner level progress
    beginner_quizzes = Quiz.objects.filter(attendees=user, level="Beginner", mark__gte=6).count()
    beginner_progress = 100 if beginner_quizzes > 0 else 0

    # Intermediate level progress
    intermediate_quizzes = Quiz.objects.filter(attendees=user, level="Intermediate", mark__gte=6).count()
    intermediate_progress = 100 if intermediate_quizzes > 0 else 0

    # Advanced level progress
    advanced_quizzes = Quiz.objects.filter(attendees=user, level="Advanced", mark__gte=6).count()
    advanced_progress = 100 if advanced_quizzes > 0 else 0

    # Save or update progress
    user_progress, created = UserProgress.objects.get_or_create(user=user, user_course=user_course)
    user_progress.beginner_progress = beginner_progress
    user_progress.intermediate_progress = intermediate_progress
    user_progress.advanced_progress = advanced_progress
    user_progress.save()

    # Calculate total progress as the average of the three levels
    total_progress = (beginner_progress + intermediate_progress + advanced_progress) / 3

    
    total_progress = math.floor(total_progress / 10) * 10  

    total_stars = 0  # Default star count

    if total_progress >= 80:
        total_stars = 3
    elif total_progress >= 50:
        total_stars = 2
    elif total_progress >= 20:
        total_stars = 1

    # Determine the pending topics based on progress
    pending_topics = []

    if beginner_progress < 100:
        pending_topics.append('Beginner')  # Show Beginner level if not completed
    if intermediate_progress < 100:
        pending_topics.append('Intermediate')  # Show Intermediate level if not completed
    if advanced_progress < 100:
        pending_topics.append('Advanced')  # Show Advanced level if not completed

    # Send the total progress and star ratings to the template
    return render(request, 'accounts/track_progress.html', {
        'data': user_progress,
        'total_progress': total_progress,  # Now rounded down to the nearest 10
        'total_stars': total_stars,
        'pending_topics': pending_topics,
        'suggested_courses': [],
    })



@login_required
def rewards_and_quizzes(request):
    user = request.user

    # Quizzes user has attended, grouped by level
    beginner_attended = Quiz.objects.filter(attendees=user, level="Beginner", mark__gte=6)
    intermediate_attended = Quiz.objects.filter(attendees=user, level="Intermediate", mark__gte=6)
    advanced_attended = Quiz.objects.filter(attendees=user, level="Advanced", mark__gte=6)

    beginner_pending = Quiz.objects.filter(level="Beginner").exclude(attendees=user)
    intermediate_pending = Quiz.objects.filter(level="Intermediate").exclude(attendees=user)
    advanced_pending = Quiz.objects.filter(level="Advanced").exclude(attendees=user)

    attended_quizzes = []
    pending_quizzes = []

    if advanced_attended.exists():
        attended_quizzes = Quiz.objects.filter(attendees=user).order_by('-date_created')[:30]
        pending_quizzes = []
    elif intermediate_attended.exists():
        attended_quizzes = Quiz.objects.filter(attendees=user, level__in=["Beginner", "Intermediate"]).order_by('-date_created')[:20]
        pending_quizzes = advanced_pending[:10]
    elif beginner_attended.exists():
        attended_quizzes = beginner_attended.order_by('-date_created')[:10]
        pending_quizzes = list(intermediate_pending[:10]) + list(advanced_pending[:10])
    else:
        # New user
        attended_quizzes = []
        pending_quizzes = list(beginner_pending[:10]) + list(intermediate_pending[:10]) + list(advanced_pending[:10])

    # Progress-based star system
    beginner_progress = 100 if beginner_attended.exists() else 0
    intermediate_progress = 100 if intermediate_attended.exists() else 0
    advanced_progress = 100 if advanced_attended.exists() else 0
    total_progress = (beginner_progress + intermediate_progress + advanced_progress) / 3

    if total_progress >= 80:
        total_stars = 3
    elif total_progress >= 50:
        total_stars = 2
    elif total_progress >= 20:
        total_stars = 1
    else:
        total_stars = 0

    context = {
        'attended_quizzes': attended_quizzes,
        'pending_quizzes': pending_quizzes,
        'total_stars': total_stars,
    }

    return render(request, 'accounts/rewards_and_quizzes.html', context)



class UserCourseAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'progress', 'rewards_earned')
    search_fields = ('user__username', 'course__name')
    list_filter = ('progress', 'rewards_earned')

    # Add a custom admin view
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('report/', self.generate_report),
        ]
        return custom_urls + urls

    def generate_report(self, request):
        # Generate a report of user courses and progress
        report_data = UserCourse.objects.all()
        # Generate a response or file
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="user_course_report.csv"'

        # Here you can add logic to generate a CSV or other formats
        response.write('User, Course, Progress\n')
        for user_course in report_data:
            response.write(f'{user_course.user.username}, {user_course.course.name}, {user_course.progress}\n')

        return response



# Load model once globally to avoid reloading it for every request
clf = joblib.load(r"C:/Users/Farooq/OneDrive/Desktop/ProjectFolder/Source-Code/SmartLearnProject/frontend/lmsproject/classification_model.pkl")

# Course Recommendation View
def course_recommendation(request):
    if request.method == 'POST':
        try:
            # Get data from the form
            age = int(request.POST.get("age"))
            degree = request.POST.get("degree")
            gpa = float(request.POST.get("gpa"))
            module = request.POST.get("module")
            time = float(request.POST.get("time"))
            roadmap_type = request.POST.get("roadmap_type", "fixed")

            # Get the selected courses from the form (checkboxes)
            selected_courses = request.POST.getlist("course")
            no_option_selected = request.POST.get("no_option")

            # --- Store preferences in session ---
            user_preferences = {
                'age': age,
                'degree': degree,
                'gpa': gpa,
                'module_preference': module, # Store module preference
                'time_available_hrs': time,
            }
            request.session['user_course_preferences'] = user_preferences
            print(f"--- Stored preferences in session: {user_preferences} ---") # Debug print
            # --- End store in session ---

            # Create DataFrame for the user input
            new_data = pd.DataFrame({
                'Age': [age],
                'Degree': [degree],
                'GPA': [gpa],
                'Learning Module Preference': [module],
                'Time Spent Daily (hrs)': [time]
            })

            # Encode categorical fields
            categorical_columns = ['Degree', 'Learning Module Preference']
            encoder = LabelEncoder()
            for col in categorical_columns:
                if new_data[col].dtype == 'object':
                     try:
                         new_data[col] = encoder.fit_transform(new_data[col].astype(str))
                     except ValueError as ve:
                         # Handle unseen labels more gracefully
                         messages.error(request, f"Invalid value provided for {col}. Please select from available options.")
                         return render(request, 'accounts/courses.html', {'error': f"Invalid value for {col}"})

            # If "No Option" is selected, recommend all domains based on the model
            if no_option_selected:
                # Get the recommendation from the model (may depend on your model's output)
                prediction = clf.predict(new_data)[0]
                # Optional: split comma-separated domains if your model returns such output
                recommended_domains = [domain.strip() for domain in prediction.split(',')]
            elif selected_courses:
                # If specific courses are selected, recommend based on them
                recommended_domains = selected_courses
            else:
                # If no courses are selected, prompt the user to select one
                recommended_domains = ["No courses selected. Please choose one."]

            if not recommended_domains:
                 # This might happen if 'no_option' was selected but prediction failed/was empty
                 messages.error(request, "Could not determine recommendations. Please check your inputs or select courses.")
                 return render(request, 'accounts/courses.html')

            # Now, perform the redirect based on roadmap_type
            if roadmap_type == "flexible":
                # --- CHANGE THIS PART ---
                # Redirect to flexible roadmap page, PASSING the domains
                print("--- DEBUG: Redirecting to flexible_temp WITH domains ---")
                domains_param = ",".join(recommended_domains) # Join list into string
                # Construct URL using reverse and add the query parameter
                redirect_url = f"{reverse('flexible_temp')}?recommended_domains={domains_param}"
                return redirect(redirect_url)
                # --- END CHANGE ---

            else: # Fixed roadmap (or default) - This part remains the same
                print("--- DEBUG: Redirecting to your_course ---")
                domains_param = ",".join(recommended_domains)
                redirect_url = f'{reverse("your_course")}?recommended_domains={domains_param}'
                return redirect(redirect_url)

        except Exception as e:
            return render(request, 'accounts/courses.html', {'error': str(e)})

    return render(request, 'accounts/courses.html')

# flexible_roadmap
def flexible_roadmap_placeholder(request):
    # This view handles the redirect when roadmap_type is "flexible"
    # Add logic here for what should happen on this page
    # You might want to access query parameters if you pass recommended_domains
    # domains = request.GET.get('recommended_domains', '')
    # ... process domains ...
    return render(request, 'accounts/flexible_roadmap_temp.html') # Example template

#personalized_course
def personalized_courses_view(request):
    print(f"--- DEBUG: model_gemini object: {model_gemini} ---")
    """
    Handles selection, GETS OR CREATES the course using AI if needed,
    enrolls user, and displays course details with AI roadmap.
    """
    course_to_display = None
    selected_domain_name = None
    is_enrolled = False
    generated_roadmap_text = "Roadmap generation pending or not applicable." # Default
    topics = [] # Default

    if request.method == 'POST':
        selected_domain_name = request.POST.get('selected_flexible_domain')

        if not selected_domain_name:
            messages.error(request, "No course selected.")
            return redirect('course_recommendation')

        try:
            # --- Try to Get or Create the Course ---
            # Provide defaults for fields needed if creating
            # Note: Using selected_domain_name for 'topic' field, adjust if needed
            course_defaults = {
                'description': f"A course about {selected_domain_name}.", # Placeholder description
                'topic': selected_domain_name # Default topic based on name
            }
            course_to_display, course_created = Course.objects.get_or_create(
                name=selected_domain_name,
                defaults=course_defaults
            ) #

            print(f"--- Course '{selected_domain_name}' - Existed: {not course_created} ---")

            # --- Enroll User ---
            user_course, enrolled_now = UserCourse.objects.get_or_create(
                user=request.user,
                course=course_to_display
            )
            is_enrolled = True
            if enrolled_now:
                 messages.success(request, f"Successfully enrolled in {course_to_display.name}!")
            else:
                 messages.info(request, f"You are already enrolled in {course_to_display.name}.")

            # --- Generate AI content ONLY if course is NEWLY created ---
            # --- OR always generate roadmap text for display (optional) ---
            roadmap_needed = True # Let's always generate the roadmap text for display
            ai_content_generated = False

            if course_created or roadmap_needed: # Check if we need to call AI
                  generated_roadmap_text = "Roadmap generation pending or not applicable."
            if model_gemini:
                # --- RETRIEVE PREFERENCES FROM SESSION ---
                user_prefs = request.session.get('user_course_preferences', {}) # Get prefs, default to empty dict
                print(f"--- Retrieved preferences from session: {user_prefs} ---") # Debug print
                # --- END RETRIEVE ---

                # Fetch user profile (Optional, basic info like name)
                user_profile = None
                try:
                    user_profile = StudentProfile.objects.get(user=request.user)
                except StudentProfile.DoesNotExist:
                    pass # Okay if profile doesn't exist

                existing_topics = Topic.objects.filter(course=course_to_display).order_by('id')

                # --- Pass user_prefs to prompt function ---
                prompt = generate_roadmap_prompt(
                    course_name=course_to_display.name,
                    user_profile=user_profile, # Pass basic profile if needed
                    user_prefs=user_prefs,      # Pass detailed preferences
                    existing_topics=existing_topics
                )

                try:
                    # ... (Call Gemini API) ...
                    print(f"--- Sending Prompt to Gemini for {course_to_display.name} (with FORM context) ---") # Debug msg
                    response = model_gemini.generate_content(prompt)
                    # ... (Process response, parse, update course if created, etc.) ...
                    raw_ai_response = response.text if response and hasattr(response, 'text') else None
                    if raw_ai_response:
                        parsed_data = parse_ai_response(raw_ai_response)
                        generated_roadmap_text = parsed_data.get('roadmap_text', "AI could not generate roadmap details.")
                        if course_created:
                            # ...(logic to update course description and create topics)...
                            if parsed_data.get('description'):
                                course_to_display.description = parsed_data['description']
                                course_to_display.save()
                            if parsed_data.get('topic_list'):
                                for topic_name in parsed_data['topic_list']:
                                    Topic.objects.create(name=topic_name, course=course_to_display)
                    else:
                         generated_roadmap_text = "AI response was empty."

                except Exception as e:
                    # ... (error handling for AI call) ...
                     generated_roadmap_text = f"Error calling AI to generate roadmap: {str(e)}"
                     print(f"!!! Gemini API Error: {e} !!!")

            # --- Fetch Topics for Display ---
            topics = Topic.objects.filter(course=course_to_display).order_by('id')

        except Exception as e:
            # ... (general error handling) ...
            messages.error(request, f"An error occurred: {e}")
            return redirect('course_recommendation')

    # --- Prepare Context and Render ---
    if course_to_display:
        context = {
            'course': course_to_display,
            'topics': topics,
            'is_enrolled': is_enrolled,
            'selected_domain': selected_domain_name,
            'generated_roadmap': generated_roadmap_text
        }
        return render(request, 'accounts/personalized_courses.html', context)
    else:
        return redirect('course_recommendation')

# Landing Page View
def landing_page(request):
    return render(request, 'accounts/landing_page.html')

# Login View for Both Students and Admins
def login_view(request):
    if request.method == 'POST':
            form = LoginForm(request.POST)
            if form.is_valid():
                # *** Change from 'username' to 'email' ***
                email = form.cleaned_data['email']
                password = form.cleaned_data['password']

                # *** Authenticate using email for the username parameter ***
                # Pass request as the first argument
                user = authenticate(request, username=email, password=password)

                if user:
                    login(request, user)
                    messages.success(request, f'Welcome back, {user.username}!')
                    # Redirect based on profile/role needs more specific logic
                    # based on your StudentProfile/UserProfile models
                    # For now, redirecting all to student_dashboard:
                    return redirect('student_dashboard') # Or determine redirect based on user role
                else:
                    messages.error(request, 'Invalid email or password.') # More specific error
            else:
                # Form validation failed (e.g., missing fields)
                messages.error(request, 'Invalid form submission. Please check your input.')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form})

# Signup View for New Users
def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            StudentProfile.objects.create(user=user)
            messages.success(request, 'Account created successfully! Please login.')
            return redirect('login')
        else:
            messages.error(request, 'There was an error while signing in, Try again!.')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})

# Student Dashboard (for logged-in students)
@login_required
def student_dashboard(request):

    # Get courses the current user is enrolled in
    # Ensure related 'course' data is fetched efficiently
    enrolled_user_courses = UserCourse.objects.filter(user=request.user).select_related('course')
    # Get the IDs of the courses the user is enrolled in
    enrolled_course_ids = [uc.course.id for uc in enrolled_user_courses]

    # Get all available courses, excluding the ones the user is enrolled in
    available_courses = Course.objects.exclude(id__in=enrolled_course_ids)

    context = {
        'enrolled_courses': enrolled_user_courses, # Pass the UserCourse objects
        'available_courses': available_courses,
        # 'user': request.user # 'user' is usually available by default if using RequestContext
    }
    # Ensure template path is correct (inside 'accounts' folder)
    return render(request, 'accounts/student_dashboard.html', context)

# Admin Dashboard (for logged-in admins)
@login_required
def admin_dashboard(request):
    return render(request, 'accounts/admin_dashboard.html')


# Custom Logout
def logout_view(request):
    logout(request)
    return redirect('login')

def courses_view(request):
    return render(request, 'accounts/courses.html')

# def your_course(request):
#     # Get the recommended_domains query parameter from the URL
#     recommended_domains = request.GET.get('recommended_domains', '').split(',')

#     # A dictionary that maps course names to URLs (or any other relevant information)
#     course_links = {
#         "Cloud": "/courses/cloud/",
#         "Data Science": "/courses/data-science/",
#         "Web Application": "/courses/web-application/",
#         "Python": "/courses/python/",
#         "Java": "/courses/java/",
#     }

#     # Create a list of recommended domains with their associated links
#     courses_with_links = [{"domain": domain, "link": course_links.get(domain, "#")} for domain in recommended_domains]

#     return render(request, 'accounts/your_course.html', {'courses_with_links': courses_with_links})

# def your_course(request):
#     user = request.user
#     recommended_domains = request.GET.get("recommended_domains", "")
#     domain_list = recommended_domains.split(',')

#     if request.method == 'POST':
#         selected_course_name = request.POST.get("selected_course")
#         if selected_course_name:
#             course, created = Course.objects.get_or_create(name=selected_course_name)
#             UserCourse.objects.get_or_create(user=user, course=course)
#             return redirect('profile')  # Redirect to profile after starting course

#     return render(request, 'accounts/your_course.html', {
#         'recommended_courses': domain_list
#     })

def enroll_in_course(request, course_id):
    """Handles enrolling the logged-in user in a specific course."""
    course = get_object_or_404(Course, id=course_id)
    user = request.user

    if request.method == 'POST':
        user_course, created = UserCourse.objects.get_or_create(user=user, course=course)

        if created:
            messages.success(request, f"You have successfully enrolled in {course.name}!")
        else:
            messages.info(request, f"You are already enrolled in {course.name}.")

        # *** CHANGE THE REDIRECT TARGET HERE ***
        # Redirect to the course detail page for THIS course
        return redirect('course_detail', course_id=course.id)
        # *** END CHANGE ***

    else:
        # Handling GET request - redirecting to dashboard is fine here
        messages.error(request, "Invalid request method for enrollment.")
        return redirect('student_dashboard')

@login_required
def your_course(request):
    user = request.user
    # Get recommended_domains from URL parameter
    recommended_domains = request.GET.get('recommended_domains', '').split(',')

    # Course name to link mapping
    course_links = {
        "Cloud": "/courses/cloud/",
        "Data Science": "/courses/data-science/",
        "Web Application": "/courses/web-application/",
        "Python": "/courses/python/",
        "Java": "/courses/java/",
    }

    # List of course dictionaries with name and link
    courses_with_links = [
        {"domain": domain.strip(), "link": course_links.get(domain.strip(), "#")}
        for domain in recommended_domains if domain.strip()
    ]

    if request.method == 'POST':
        selected_course_name = request.POST.get("selected_course")
        if selected_course_name:
            # Save to database (if not already saved)
            course, created = Course.objects.get_or_create(name=selected_course_name)
            UserCourse.objects.get_or_create(user=user, course=course)

            # Redirect to course-specific page
            course_link = course_links.get(selected_course_name)
            if course_link:
                return redirect(course_link)
            else:
                return redirect('profile')  # fallback if no link

    return render(request, 'accounts/your_course.html', {
        'courses_with_links': courses_with_links,
        'recommended_courses': recommended_domains
    })

@login_required # Make sure course pages require login
def java_course(request):
    course = get_object_or_404(Course, name="Java") # Fetch course by name
    is_enrolled = UserCourse.objects.filter(user=request.user, course=course).exists()
    context = {
        'course': course,
        'is_enrolled': is_enrolled
    }
    return render(request, 'courses/java.html', context)

@login_required
def python_course(request):
    course = get_object_or_404(Course, name="Python") # Fetch course by name
    is_enrolled = UserCourse.objects.filter(user=request.user, course=course).exists()
    context = {
        'course': course,
        'is_enrolled': is_enrolled
    }
    return render(request, 'courses/python.html', context)

@login_required
def cloud_course(request):
    course = get_object_or_404(Course, name="Cloud Computing") # Fetch course by name
    is_enrolled = UserCourse.objects.filter(user=request.user, course=course).exists()
    context = {
        'course': course,
        'is_enrolled': is_enrolled
    }
    return render(request, 'courses/cloud.html', context)

@login_required
def data_science_course(request):
    course = get_object_or_404(Course, name="Data Science") # Fetch course by name
    is_enrolled = UserCourse.objects.filter(user=request.user, course=course).exists()
    context = {
        'course': course,
        'is_enrolled': is_enrolled
    }
    return render(request, 'courses/data_science.html', context)

@login_required
def web_application_course(request):
    # Assuming the course name in the DB is 'Web Application' based on previous views
    course = get_object_or_404(Course, name="Web Application") # Fetch course by name
    is_enrolled = UserCourse.objects.filter(user=request.user, course=course).exists()
    context = {
        'course': course,
        'is_enrolled': is_enrolled
    }
    return render(request, 'courses/web_application.html', context)

@login_required
def course_detail_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    is_enrolled = UserCourse.objects.filter(user=request.user, course=course).exists()
    topics = Topic.objects.filter(course=course) # Fetch related topics

    # You might fetch related quizzes here too if they are linked to Course/Topic
    # beginner_quiz_url = ... # Logic to find the right quiz URL

    print(f"\n--- DETAIL VIEW DEBUG ---")
    print(f"Current User ID: {request.user.id}")
    print(f"Current Username: {request.user.username}")
    print(f"Course ID: {course.id}")
    print(f"Course Name: {course.name}")
    # Print the result of the check we just did
    print(f"Result of UserCourse.objects.filter(...).exists(): {is_enrolled}")
    print(f"--- END DETAIL VIEW DEBUG ---\n")

    context = {
        'course': course,
        'is_enrolled': is_enrolled,
        'topics': topics,
        # Add other relevant data like quiz URLs if determined
    }
    return render(request, 'course_detail.html', context)

@login_required
def beginner_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                
                    name=request.user.username,
                    level="Beginner",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('java_intermediate_quiz')

                return JsonResponse({
                    'message': 'Great job! You passed the Java beginner quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/java_beginner_quiz.html')

@login_required
def intermediate_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                  
                    name=request.user.username,
                    level="Intermediate",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('java_advanced_quiz')

                return JsonResponse({
                    'message': 'Great job! You passed the intermediate Java quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/java_intermediate_quiz.html')

@login_required
def advanced_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                    
                    name=request.user.username,
                    level="Advanced",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('java_advanced_quiz')  # or another final summary page

                return JsonResponse({
                    'message': 'Awesome! You completed the advanced Java quiz!' if score >= 6 else 'Review and try again!',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/java_advanced_quiz.html')

@login_required
def python_beginner_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                    name=request.user.username,
                    level="Beginner",
                    mark=score,
                )
                quiz.attendees.add(request.user)  # Add user to many-to-many field

                redirect_url = reverse('python_intermediate_quiz')  # Change this if you need

                return JsonResponse({
                    'message': 'Great job! You passed the quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return render(request, 'accounts/python_beginner_quiz.html')

@login_required
def python_intermediate_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                    name=request.user.username,
                    level="Intermediate",
                    mark=score,
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('python_advanced_quiz')  # Go to advanced quiz

                return JsonResponse({
                    'message': 'Great job! You passed the intermediate quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/python_intermediate_quiz.html')

@login_required
def python_advanced_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                    name=request.user.username,
                    level="Advanced",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('python_advanced_quiz')  # Final step → show progress page

                return JsonResponse({
                    'message': 'Awesome! You completed the advanced quiz!' if score >= 6 else 'Review and try again!',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/python_advanced_quiz.html')

@login_required
def cloud_computing_beginner_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                    name=request.user.username,
                    level="Beginner",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('cloud_computing_intermediate_quiz')

                return JsonResponse({
                    'message': 'Great job! You passed the beginner quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/cloud_computing_beginner_quiz.html')

@login_required
def cloud_computing_intermediate_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                    name=request.user.username,
                    level="Intermediate",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('cloud_computing_advanced_quiz')

                return JsonResponse({
                    'message': 'Great work! You passed the intermediate quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/cloud_computing_intermediate_quiz.html')

@login_required
def cloud_computing_advanced_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                   
                    name=request.user.username,
                    level="Advanced",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('cloud_computing_advanced_quiz')  # Or wherever you want after advanced

                return JsonResponse({
                    'message': 'Congratulations! You have completed all levels.' if score >= 6 else 'Keep going, you can do it!',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/cloud_computing_advanced_quiz.html')

@login_required
def data_science_beginner_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')
            
            if score is not None:
                quiz = Quiz.objects.create(
                    name=request.user.username,
                    level="Beginner",
                    mark=score
                )
                quiz.attendees.add(request.user)

                if score >= 6:
                    # Redirect to Intermediate Level
                    redirect_url = reverse('data_science_intermediate_quiz')  
                    message = 'Great job! You passed the beginner quiz!'
                else:
                    redirect_url = None
                    message = 'Try again to improve your score.'

                return JsonResponse({
                    'message': message,
                    'status': 'success',
                    'redirect_url': redirect_url
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    else:
        return render(request, 'accounts/data_science_beginner_quiz.html')

@login_required
def data_science_intermediate_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                   
                    name=request.user.username,
                    level="Intermediate",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('data_science_advanced_quiz')

                return JsonResponse({
                    'message': 'Awesome! You can now advance to the final quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'Score not provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/data_science_intermediate_quiz.html')

@login_required
def data_science_advanced_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                # Create the Quiz record
                quiz = Quiz.objects.create(
                    name=request.user.username,
                    level="Advanced",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('web_development_advanced_quiz')  # or dashboard/final summary

                return JsonResponse({
                    'message': 'Awesome! You completed the advanced quiz!' if score >= 6 else 'Review and try again!',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    else:
        return render(request, 'accounts/data_science_advanced_quiz.html')

@login_required
def web_development_beginner_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                   
                    name=request.user.username,
                    level="Beginner",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('web_development_intermediate_quiz')

                return JsonResponse({
                    'message': 'Great job! You passed the beginner quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/web_development_beginner_quiz.html')

@login_required
def web_development_intermediate_quiz_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')

            if score is not None:
                quiz = Quiz.objects.create(
                    
                    name=request.user.username,
                    level="Intermediate",
                    mark=score
                )
                quiz.attendees.add(request.user)

                redirect_url = reverse('web_development_advanced_quiz')

                return JsonResponse({
                    'message': 'Great job! You passed the intermediate quiz!' if score >= 6 else 'Try again to improve your score.',
                    'status': 'success',
                    'redirect_url': redirect_url if score >= 6 else ''
                })
            else:
                return JsonResponse({'error': 'No score provided'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return render(request, 'accounts/web_development_intermediate_quiz.html')

@login_required
def web_development_advanced_quiz_view(request):
    # Inside the advanced quiz view's POST handler...
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            score = data.get('score')
            print(f"Received score: {score}") # Print received score

            if score is not None:
                total_questions = 10 # Adjust if needed
                percentage = (score / total_questions) * 100 if total_questions > 0 else 0
                print(f"Calculated percentage: {percentage:.2f}%") # Print calculated percentage

                if percentage >= 40:
                    print("--- Score >= 40%, attempting to mark complete ---")
                    try:
                        course_name = "Web Development" # <<< DOUBLE CHECK THIS NAME MATCHES DB EXACTLY for this view
                        print(f"Attempting to find course: '{course_name}'")
                        course = Course.objects.get(name=course_name) 
                        print(f"Found course: {course}")
                        
                        print(f"Attempting to get/create UserCourse for user {request.user.id} and course {course.id}")
                        user_course, created = UserCourse.objects.get_or_create(user=request.user, course=course)
                        print(f"Got UserCourse: {user_course}, Created new: {created}")

                        print(f"Setting progress to 100 (current is {user_course.progress})")
                        user_course.progress = 100 
                        
                        print("Attempting to save UserCourse...")
                        user_course.save() # <<< ENSURE THIS LINE EXISTS
                        print("--- UserCourse saved successfully! ---") 
                        
                        return JsonResponse({ ... }) # Your existing JSON response

                    except Course.DoesNotExist:
                         # --- ADD PRINT ---
                         print(f"!!! ERROR: Course '{course_name}' not found in database! !!!")
                         return JsonResponse({'error': 'Course not found for completion tracking.'}, status=404)
                    except UserCourse.DoesNotExist: 
                         # Should not happen with get_or_create, but good to have
                         print(f"!!! ERROR: UserCourse not found and couldn't be created? !!!")
                         return JsonResponse({'error': 'User enrollment not found for completion tracking.'}, status=404)
                    except Exception as e:
                         # --- ADD PRINT ---
                         print(f"!!! ERROR during completion update: {type(e).__name__} - {e} !!!")
                         # Log the full exception 'e' here if needed
                         return JsonResponse({'error': 'Error updating course completion.'}, status=500)
                        
                else: # Score < 40%
                    print("--- Score < 40%, processing as retry ---")
                    # ... (your existing logic for handling low score quiz attempt logging) ...
                    return JsonResponse({ ... }) # Your existing JSON response for retry

            else: # Score is None
                print("!!! ERROR: Score not found in POST data! !!!")
                return JsonResponse({'error': 'No score provided'}, status=400)
                
        except Exception as e: # Catch broader errors loading JSON etc.
             # --- ADD PRINT ---
             print(f"!!! ERROR processing POST request: {type(e).__name__} - {e} !!!")
             # Log the exception 'e'
             return JsonResponse({'error': str(e)}, status=500)
             
    else: # GET Request
        print("--- Handling GET request, rendering template ---")
        return render(request, 'accounts/web_development_advanced_quiz.html') # Adjust template path
    
@login_required
def flexible_roadmap_placeholder(request):
    domains_param = request.GET.get('recommended_domains', '') # Default to empty string if not found

    # Split the string back into a list, handling empty strings/parameter
    if domains_param:
        recommended_domains_list = [domain.strip() for domain in domains_param.split(',') if domain.strip()]
    else:
        recommended_domains_list = []

    # Pass the list to the template context
    context = {
        'domains': recommended_domains_list
    }
    # --- END ADDED LOGIC ---

    # Render the template, passing the context
    return render(request, 'accounts/flexible_roadmap_temp.html', context)