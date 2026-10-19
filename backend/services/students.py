from data.mock_students import mock_profiles


def get_student_profile(student_id: int):
    return mock_profiles.get(student_id)
