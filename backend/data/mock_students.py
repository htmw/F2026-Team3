# Mock data for local development only
mock_profiles = {
    101: {
        "student": {
            "student_id": 101,
            "name": "John Smith",
            "email": "john@example.com",
            "program_id": 1,
            "program_name": "MS Computer Science",
            "gpa": 3.5,
            "completed_credits": 6,
            "total_required_credits": 30
        },
        "enrollments": [
            {
                "enrollment_id": 301,
                "course_id": 11,
                "course_code": "CS601",
                "course_name": "Introduction to Computing",
                "term": "Fall 2025",
                "credits": 3,
                "status": "completed",
                "grade": "A",
                "grade_points": 4.0
            },
            {
                "enrollment_id": 302,
                "course_id": 12,
                "course_code": "CS602",
                "course_name": "Computer Systems",
                "term": "Spring 2026",
                "credits": 3,
                "status": "completed",
                "grade": "B",
                "grade_points": 3.0
            }
        ]
    }
}