from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
import logging

logger = logging.getLogger(__name__)

class EmailOrUsernameModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        
        try:
            # Try to find the user by email (case-insensitive)
            user = UserModel.objects.get(email__iexact=username)
            logger.info(f"User found by email: {user.username}")
            if user.check_password(password):
                logger.info("Password is correct")
                return user
            else:
                logger.warning("Incorrect password")
                return None
        except UserModel.DoesNotExist:
            logger.warning(f"No user found with email: {username}")
            # If no user found by email, try username
            try:
                user = UserModel.objects.get(username__iexact=username)
                logger.info(f"User found by username: {user.username}")
                if user.check_password(password):
                    logger.info("Password is correct")
                    return user
                else:
                    logger.warning("Incorrect password")
                    return None
            except UserModel.DoesNotExist:
                logger.warning(f"No user found with username: {username}")
                return None
        except UserModel.MultipleObjectsReturned:
            logger.error(f"Multiple users found with email: {username}")
            return None