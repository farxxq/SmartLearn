# SmartLearn Project

## Overview

SmartLearn is a web-based Learning Management System (LMS) designed to facilitate a personalized learning experience. The platform offers functionalities such as course enrollment, progress tracking, difficulty-categorized quizzes, and a machine learning-driven course recommendation system. The frontend is developed using Django with Bootstrap for styling, while the backend incorporates a classification model for personalization.

## Features

- **User Authentication:** Secure registration and login mechanisms.
- **Student Dashboard:** A personalized dashboard presenting enrolled courses, available courses, progress indicators, and achievement rewards.
- **Course Management:** Functionality to browse courses (Python, Java, Data Science, Cloud Computing, Web Development), review course details, and enroll in courses.
- **Quizzes:** Assessments at Beginner, Intermediate, and Advanced levels across various subjects.
- **Progress Tracking:** Monitoring of course and quiz completion, including an achievement reward system.
- **Course Recommendations:** Personalized course suggestions derived from user profile data via a machine learning model.
- **Admin Dashboard:** A basic administrative interface.

## Technology Stack

- **Backend:** Python, Django
- **Machine Learning:** Scikit-learn, Pandas, Joblib
- **Frontend:** HTML, CSS, JavaScript, Bootstrap
- **Database:** SQLite (default Django database)

## Requirements

- Python (Version 3.11 recommended, as per environment)
- `pip` (Python package installer)
- `virtualenv` (Recommended for dependency isolation)
- Python Packages:

  - `django`
  - `pandas`
  - `scikit-learn`
  - `joblib`
  - _(Optional, for ML notebook execution)_ `numpy`, `seaborn`, `matplotlib`

  _Note: Creation of a `requirements.txt` file is highly recommended._

  ```bash
  pip freeze > requirements.txt
  ```

  _Installation can be performed using:_

  ```bash
  pip install -r requirements.txt
  ```

## Setup Instructions

1.  **Repository Cloning (or File Download):**

    ```bash
    # Replace with the repository URL if applicable
    git clone <repository-url>
    cd SmartLearnProject
    ```

    _(If a ZIP archive was downloaded, extract the contents and navigate to the `SmartLearnProject` directory)_

2.  **Navigation to the Django Project Directory:**

    ```bash
    cd frontend/lmsproject
    ```

3.  **Virtual Environment Creation and Activation (Recommended):**

    - On macOS/Linux:
      ```bash
      python3 -m venv venv
      source venv/bin/activate
      ```
    - On Windows:
      ```bash
      python -m venv venv
      .\venv\Scripts\activate
      ```

4.  **Installation of Required Packages:**

    - _If a `requirements.txt` file was generated:_
      ```bash
      pip install -r requirements.txt
      ```
    - _Otherwise, manual installation:_
      ```bash
      pip install django pandas scikit-learn joblib
      ```

5.  **Database Migrations Application:**
    _(Ensure the current directory is `frontend/lmsproject` where `manage.py` resides)_

    ```bash
    python manage.py makemigrations accounts
    python manage.py migrate
    ```

6.  **Superuser Creation (Optional but Recommended):**
    _(Facilitates access to the Django admin interface `/admin/`)_

    ```bash
    python manage.py createsuperuser
    ```

    _(Follow the prompts to configure username, email, and password)_

7.  **Machine Learning Model Setup:**
    - The course recommendation feature relies on a trained model file named `classification_model.pkl`.
    - This file can be generated by executing the Jupyter notebook located at `backend/hybridmodel code.ipynb`. Ensure the required libraries (`numpy`, `seaborn`, `matplotlib`, etc.) are installed.
    - **IMPORTANT:** The model loading path is currently hardcoded within `accounts/views.py` to a specific user directory. This path must be updated.
      - **Recommendation:**
        1.  Place the generated `classification_model.pkl` file within the `accounts` application directory (e.g., `frontend/lmsproject/accounts/classification_model.pkl`).
        2.  Modify the `joblib.load(...)` line in `accounts/views.py` (around line 259) to utilize a relative path derived from Django's settings:
            ```python
            import os
            from django.conf import settings
            # ... within the course_recommendation view or globally ...
            model_path = os.path.join(settings.BASE_DIR, 'accounts', 'classification_model.pkl')
            # Utilize model_path instead of the hardcoded path:
            clf = joblib.load(model_path)
            ```

## Project Execution

1.  **Initiation of the Django Development Server:**
    _(Ensure the `frontend/lmsproject` directory is the current directory and the virtual environment is activated)_

    ```bash
    python manage.py runserver
    ```

2.  **Application Access:**
    - Open a web browser and navigate to: `http://127.0.0.1:8000/` or `http://localhost:8000/`
    - The landing page should be rendered. User registration or login is supported.
    - The administrative interface is accessible at `http://127.0.0.1:8000/admin/`.
