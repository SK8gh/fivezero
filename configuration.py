from singleton_decorator import singleton


# Bot username
USERNAME = "FiveZero"

# Main API url
API = "https://api-connect5.dev.codebusters.cloud"

# Logging route
LOGIN_URL = f"{API}/api/auth/login"

# Hub route
GAME_HUB_URL = f"{API}/gameHub"


@singleton
class EngineConfig:
    def __init__(self, max_time, max_depth):
        # maximum engine depth when performing searches
        self.max_depth: int = max_depth

        # maximum thinking time in seconds when performing searches
        self.max_time: int = max_time
