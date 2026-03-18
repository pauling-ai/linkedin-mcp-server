"""Custom exceptions for LinkedIn scraping operations."""


class LinkedInScraperException(Exception):
    """Base exception for LinkedIn scraper."""

    pass


class AuthenticationError(LinkedInScraperException):
    """Raised when authentication fails."""

    pass


class ElementNotFoundError(LinkedInScraperException):
    """Raised when an expected element is not found."""

    pass


class ProfileNotFoundError(LinkedInScraperException):
    """Raised when a profile/page returns 404."""

    pass


class NetworkError(LinkedInScraperException):
    """Raised when network-related issues occur."""

    pass


class ScrapingError(LinkedInScraperException):
    """Raised when scraping fails for various reasons."""

    pass
