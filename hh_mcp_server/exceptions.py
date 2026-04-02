class HHMCPError(Exception):
    pass


class AuthenticationError(HHMCPError):
    def __init__(self, message: str = "Session expired. Run: hh-mcp-server --login"):
        super().__init__(message)


class ScrapingError(HHMCPError):
    pass


class ApplyError(HHMCPError):
    pass
