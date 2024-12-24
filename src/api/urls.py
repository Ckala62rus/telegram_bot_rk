from config.configuration import settings


class ApiUrls:
    baseUrl: str = settings.LARAVEL_API_URL
    executeCommand: str = '/www'


apiUrls = ApiUrls()
