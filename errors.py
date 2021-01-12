class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class RobotError(Error):
    """Exception raised for robot detection (solvable).

    Attributes:
        message -- explanation of the error
    """

    def __init__(self):
        self.message = "Robot Check Detected."

class AQError(Error):
    """Exception raised for auto-query detection.

    Attributes:
        message -- explanation of the error.
    """

    def __init__(self):
        self.message = "Automated Queries Check Detected."

class SearchError(Error):
    """Exception raised for empty search results.

    Attributes:
        message -- explanation of the error.
    """

    def __init__(self):
        self.message = "No search results."

class GScholarError(Error):
    """Exception raised for auto-query detection.

    Attributes:
        message -- explanation of the error (non-solvable).
    """

    def __init__(self):
        self.message = "No more alternative addresses. Restart this program."