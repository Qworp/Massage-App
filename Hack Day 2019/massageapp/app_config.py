import os

USERNAME = os.getenv('USERNAME')

PASSWORD = os.getenv('PASSWORD')

CLIENT_SECRET = os.getenv("CLIENT_SECRET")

TENANT = os.getenv('TENANT')

AUTHORITY = "https://login.microsoftonline.com/common"

TENANT_AUTHORITY = 'https://login.microsoftonline.com/{}'.format(TENANT)

CLIENT_ID = os.getenv('CLIENT_ID')

ENDPOINT = os.getenv("ENDPOINT")

SCOPE = ["User.ReadBasic.All", "Calendars.ReadWrite"]

SESSION_TYPE = "filesystem"  # So token cache will be stored in server-side session
