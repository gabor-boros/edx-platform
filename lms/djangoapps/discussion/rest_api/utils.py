"""
Utils for discussion API.
"""


import functools
from datetime import datetime

from django.core.exceptions import ValidationError
from opaque_keys.edx.keys import CourseKey
from pytz import UTC

from lms.djangoapps.courseware.courses import get_course_by_id
from lms.djangoapps.discussion.django_comment_client.utils import (
    has_discussion_privileges,
    JsonError
)
from openedx.core.djangoapps.django_comment_common.comment_client.thread import Thread


def discussion_accessible(endpoint_flag):
    """
    View decorator (with argument) to check if discussions are accessible to user.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """
            Wrapper for the view that calls the view only if the user has privileges
            and discussions are accessible.
            """
            def get_course_from_context():
                """
                Returns course that is calculated from context from request.
                :return:
                """
                if endpoint_flag == 'threads':
                    try:
                        course_id = request.data['course_id']
                    except KeyError as err:
                        raise ValidationError({"course_id": ["This field is required."]}) from err
                else:   # for now we only have 2 places where the decorator is used.
                    try:
                        course_id = Thread(id=request.data['thread_id']).retrieve('course_id').get('course_id')
                    except KeyError as err:
                        raise ValidationError({"thread_id": ["This field is required."]}) from err

                course_key = CourseKey.from_string(course_id)
                course_from_context = get_course_by_id(course_key)
                return course_from_context

            def is_discussion_blacked():
                """
                Check if discussion is in blackout period or not.
                """
                is_discussion_in_blackout = False
                for blackout in course.get_discussion_blackout_datetimes():
                    if blackout['start'] < datetime.now(UTC) < blackout['end']:
                        is_discussion_in_blackout = True
                return is_discussion_in_blackout

            request = args[0]
            user = request.user
            course = get_course_from_context()
            is_user_privileged = has_discussion_privileges(user, course.id)
            is_discussion_blacked_out = is_discussion_blacked()
            if is_discussion_blacked_out and not is_user_privileged:
                return JsonError('Discussions are in a black out period.', status=403)

            return func(*args, **kwargs)

        return wrapper
    return decorator
