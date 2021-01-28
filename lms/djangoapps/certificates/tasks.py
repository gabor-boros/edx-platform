"""
Module for generating certificate for a user
"""


from logging import getLogger

from celery import shared_task  # lint-amnesty, pylint: disable=import-error
from celery_utils.persist_on_failure import LoggedPersistOnFailureTask  # lint-amnesty, pylint: disable=import-error
from django.contrib.auth.models import User  # lint-amnesty, pylint: disable=imported-auth-user
from edx_django_utils.monitoring import set_code_owner_attribute  # lint-amnesty, pylint: disable=import-error
from opaque_keys.edx.keys import CourseKey  # lint-amnesty, pylint: disable=import-error

from lms.djangoapps.certificates.api import generate_user_certificates
from lms.djangoapps.verify_student.services import IDVerificationService

logger = getLogger(__name__)


@shared_task(base=LoggedPersistOnFailureTask, bind=True, default_retry_delay=30, max_retries=2)
@set_code_owner_attribute
def generate_certificate(self, **kwargs):
    """
    Generates a certificate for a single user.

    kwargs:
        - student: The student for whom to generate a certificate.
        - course_key: The course key for the course that the student is
            receiving a certificate in.
        - expected_verification_status: The expected verification status
            for the user.  When the status has changed, we double check
            that the actual verification status is as expected before
            generating a certificate, in the off chance that the database
            has not yet updated with the user's new verification status.
    """
    original_kwargs = kwargs.copy()
    student = User.objects.get(id=kwargs.pop('student'))
    course_key = CourseKey.from_string(kwargs.pop('course_key'))
    expected_verification_status = kwargs.pop('expected_verification_status', None)
    if expected_verification_status:
        actual_verification_status = IDVerificationService.user_status(student)
        actual_verification_status = actual_verification_status['status']
        if expected_verification_status != actual_verification_status:
            logger.warning(
                u'Expected verification status {expected} '
                u'differs from actual verification status {actual} '
                u'for user {user} in course {course}'.format(
                    expected=expected_verification_status,
                    actual=actual_verification_status,
                    user=student.id,
                    course=course_key
                ))
            raise self.retry(kwargs=original_kwargs)
    generate_user_certificates(student=student, course_key=course_key, **kwargs)
