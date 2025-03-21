"""
URL utility for parsing and manipulating URLs.
"""

import logging
import urllib.parse
import re
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

class URL:
    """Utility class for URL parsing and manipulation."""
    
    # Schemas recognized as secure
    SECURE_SCHEMAS = {'https', 'wss'}
    
    # Default ports for common schemes
    DEFAULT_PORTS = {
        'http': 80,
        'https': 443,
        'ftp': 21,
        'sftp': 22,
        'ws': 80,
        'wss': 443
    }
    
    # Special URL schemes that don't require network requests
    SPECIAL_SCHEMES = {'about', 'data', 'javascript', 'blob', 'file'}
    
    # Common file extensions for web resources
    FILE_EXTENSIONS = {
        'html', 'htm', 'php', 'asp', 'aspx', 'jsp', 'css', 'js', 'json', 
        'xml', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'pdf', 'txt'
    }
    
    def __init__(self, url: str, base_url: Optional[str] = None):
        """
        Initialize a URL object.
        
        Args:
            url: URL string to parse
            base_url: Optional base URL for resolving relative URLs
        """
        # Ensure url is a string and not None
        if url is None:
            logger.warning("URL was None, using 'about:blank' as fallback")
            url = "about:blank"
        elif not isinstance(url, str):
            logger.warning(f"URL was not a string ({type(url)}), converting to string")
            url = str(url)
        
        if not url:
            url = "about:blank"
        
        # Check for known special schemes
        for scheme in self.SPECIAL_SCHEMES:
            if url.startswith(f"{scheme}:"):
                self._url = url
                self._parsed = urllib.parse.urlparse(url)
                logger.debug(f"Special URL parsed: {url}")
                return
            
        # Ensure URL has scheme - default to https:// for security
        if "://" not in url:
            # Check if it looks like a domain name
            # Domain pattern: something like example.com, www.example.co.uk
            domain_pattern = re.compile(r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')
            
            # Check if it has a file extension
            has_file_extension = False
            if "." in url:
                extension = url.split(".")[-1].lower()
                # Check if the extension looks like a file extension
                has_file_extension = extension in self.FILE_EXTENSIONS or len(extension) <= 4
            
            if "." in url and not url.startswith("/") and domain_pattern.match(url):
                # Looks like a domain name (e.g., example.com)
                url = "https://" + url
            # Check if it's a relative path (starts with /, ./ or ../)
            elif url.startswith("/") or url.startswith("./") or url.startswith("../"):
                # For relative URLs, resolve against the base URL
                if base_url:
                    resolved_url = urllib.parse.urljoin(base_url, url)
                    self._url = resolved_url
                    self._parsed = urllib.parse.urlparse(resolved_url)
                    logger.debug(f"Relative URL resolved: {url} against base: {base_url} -> {resolved_url}")
                    return
                else:
                    # If no base URL, keep the relative URL as is
                    self._url = url
                    self._parsed = urllib.parse.urlparse("about:blank")
                    logger.debug(f"Relative URL parsed without base: {url}")
                    return
            # Check if it's a plain filename or path (like "about.html" or "images/logo.png")
            elif "/" in url or has_file_extension:
                # For relative URLs, resolve against the base URL
                if base_url:
                    resolved_url = urllib.parse.urljoin(base_url, url)
                    self._url = resolved_url
                    self._parsed = urllib.parse.urlparse(resolved_url)
                    logger.debug(f"Relative path resolved: {url} against base: {base_url} -> {resolved_url}")
                    return
                elif base_url.endswith("html") or base_url.endswith("htm") or base_url.endswith("php") or base_url.endswith("asp") or base_url.endswith("aspx") or base_url.endswith("jsp") or base_url.endswith("php"):
                    resolved_url = urllib.parse.urljoin(base_url, "/", url)
                    self._url = resolved_url
                    self._parsed = urllib.parse.urlparse(resolved_url)
                    logger.debug(f"Relative path parsed without base: {url}")
                    return
            # Just a search term
            else:
                # Could use a default search engine here
                url = "https://search.sparksammy.com/search.php?p=0&t=0&q=" + urllib.parse.quote(url)
        

        self._url = url
        self._parsed = urllib.parse.urlparse(url)
        
        logger.debug(f"URL parsed: {url}")

    
    @property
    def scheme(self) -> str:
        """Get the URL scheme."""
        return self._parsed.scheme
    
    @property
    def netloc(self) -> str:
        """Get the URL network location."""
        return self._parsed.netloc
    
    @property
    def hostname(self) -> Optional[str]:
        """Get the URL hostname."""
        return self._parsed.hostname
    
    @property
    def port(self) -> Optional[int]:
        """Get the URL port."""
        if self._parsed.port:
            return self._parsed.port
        
        # Return default port for scheme if known
        if self.scheme in self.DEFAULT_PORTS:
            return self.DEFAULT_PORTS[self.scheme]
        
        return None
    
    @property
    def username(self) -> Optional[str]:
        """Get the URL username."""
        return self._parsed.username
    
    @property
    def password(self) -> Optional[str]:
        """Get the URL password."""
        return self._parsed.password
    
    @property
    def path(self) -> str:
        """Get the URL path."""
        return self._parsed.path or "/"
    
    @property
    def query(self) -> str:
        """Get the URL query string."""
        return self._parsed.query
    
    @property
    def fragment(self) -> str:
        """Get the URL fragment."""
        return self._parsed.fragment
    
    @property
    def query_params(self) -> Dict[str, str]:
        """Get the URL query parameters as a dictionary."""
        if not self.query:
            return {}
        
        return dict(urllib.parse.parse_qsl(self.query))
    
    @property
    def is_secure(self) -> bool:
        """Check if the URL has a secure scheme."""
        return self.scheme in self.SECURE_SCHEMAS
    
    @property
    def is_special(self) -> bool:
        """Check if the URL is a special URL (about, data, etc.)."""
        return self.scheme in {'about', 'data', 'javascript', 'file'}
    
    @property
    def is_valid(self) -> bool:
        """Check if the URL is valid."""
        # A valid URL must have a scheme and a hostname (except for special URLs)
        if self.is_special:
            return True
        
        return bool(self.scheme and self.hostname)
    
    @property
    def normalized(self) -> str:
        """Return a normalized string representation of the URL."""
        # Special URLs should be returned as-is
        if self.is_special:
            return self._url
        
        # Create a normalized URL string
        netloc = self.netloc
        if self.port and self.port == self.DEFAULT_PORTS.get(self.scheme):
            # Remove default port
            netloc = netloc.split(':')[0]
        
        # Normalize path
        path = self._normalize_path(self.path)
        if not path.startswith('/'):
            path = '/' + path
        
        # Build the URL
        normalized = f"{self.scheme}://{netloc}{path}"
        
        # Add query if present
        if self.query:
            normalized += f"?{self.query}"
        
        # Add fragment if present
        if self.fragment:
            normalized += f"#{self.fragment}"
            
        return normalized
    
    @property
    def origin(self) -> str:
        """Get the URL origin (scheme + netloc)."""
        if self.is_special and self.scheme != 'file':
            return f"{self.scheme}:"
        
        return f"{self.scheme}://{self.netloc}"
    
    @property
    def base(self) -> str:
        """Get the URL base (scheme + netloc + path without filename)."""
        if self.path.endswith('/'):
            base_path = self.path
        else:
            base_path = self.path.rsplit('/', 1)[0] + '/'
        
        return f"{self.scheme}://{self.netloc}{base_path}"
    
    @property
    def parent(self) -> 'URL':
        """Get the parent URL (one directory up)."""
        if self.path == '/' or not self.path:
            # Already at the root
            return URL(f"{self.scheme}://{self.netloc}/")
        
        # Get the parent path
        if self.path.endswith('/'):
            parent_path = self.path.rsplit('/', 2)[0] + '/'
        else:
            parent_path = self.path.rsplit('/', 1)[0] + '/'
        
        if not parent_path.startswith('/'):
            parent_path = '/' + parent_path
        
        return URL(f"{self.scheme}://{self.netloc}{parent_path}")
    
    def join(self, path: str) -> 'URL':
        """
        Join a path to the current URL.
        
        Args:
            path: Path to join
            
        Returns:
            URL: New URL with the joined path
        """
        if not path:
            return URL(self._url)
        
        # Handle absolute URLs
        if "://" in path:
            return URL(path)
        
        # Handle absolute paths
        if path.startswith('/'):
            return URL(f"{self.scheme}://{self.netloc}{path}")
        
        # Handle special cases
        if path.startswith('#'):
            # Fragment only
            url_without_fragment = self._url.split('#')[0]
            return URL(f"{url_without_fragment}{path}")
        
        if path.startswith('?'):
            # Query only
            url_without_query = self._url.split('?')[0]
            return URL(f"{url_without_query}{path}")
        
        # Handle relative paths
        if self.path.endswith('/'):
            base = self.path
        else:
            # Remove the last path component
            base = self.path.rsplit('/', 1)[0] + '/'
        
        # Normalize the path (handle ../ and ./)
        joined_path = self._normalize_path(base + path)
        
        return URL(f"{self.scheme}://{self.netloc}{joined_path}")
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize a path, resolving '..' and '.'.
        
        Args:
            path: Path to normalize
            
        Returns:
            str: Normalized path
        """
        # Split path into components
        if path.startswith('/'):
            path = path[1:]
            leading_slash = '/'
        else:
            leading_slash = ''
        
        components = path.split('/')
        normalized = []
        
        for component in components:
            if component == '.' or not component:
                # Skip '.' or empty components
                continue
            elif component == '..':
                # Go up one level
                if normalized:
                    normalized.pop()
            else:
                # Add the component
                normalized.append(component)
        
        # Join and preserve trailing slash
        result = leading_slash + '/'.join(normalized)
        if path.endswith('/') and result:
            result += '/'
        
        return result or '/'
    
    def with_query(self, query_params: Dict[str, str]) -> 'URL':
        """
        Create a new URL with updated query parameters.
        
        Args:
            query_params: Query parameters to set
            
        Returns:
            URL: New URL with updated query parameters
        """
        # Get current query parameters
        params = self.query_params.copy()
        
        # Update with new parameters
        params.update(query_params)
        
        # Create query string
        query_string = urllib.parse.urlencode(params)
        
        # Rebuild URL
        url_parts = list(self._parsed)
        url_parts[4] = query_string
        
        return URL(urllib.parse.urlunparse(url_parts))
    
    def without_query(self) -> 'URL':
        """
        Create a new URL without query parameters.
        
        Returns:
            URL: New URL without query parameters
        """
        # Rebuild URL
        url_parts = list(self._parsed)
        url_parts[4] = ''
        
        return URL(urllib.parse.urlunparse(url_parts))
    
    def without_fragment(self) -> 'URL':
        """
        Create a new URL without the fragment.
        
        Returns:
            URL: New URL without the fragment
        """
        # Rebuild URL
        url_parts = list(self._parsed)
        url_parts[5] = ''
        
        return URL(urllib.parse.urlunparse(url_parts))
    
    @classmethod
    def encode(cls, text: str) -> str:
        """
        URL encode a string.
        
        Args:
            text: String to encode
            
        Returns:
            str: URL encoded string
        """
        return urllib.parse.quote(text)
    
    @classmethod
    def decode(cls, text: str) -> str:
        """
        URL decode a string.
        
        Args:
            text: String to decode
            
        Returns:
            str: URL decoded string
        """
        return urllib.parse.unquote(text)
    
    @classmethod
    def is_valid_url(cls, url: str) -> bool:
        """
        Check if a URL string is valid.
        
        Args:
            url: URL string to check
            
        Returns:
            bool: True if the URL is valid
        """
        try:
            return URL(url).is_valid
        except Exception:
            return False
    
    def __str__(self) -> str:
        """
        Get the string representation of the URL.
        
        Returns:
            str: URL string
        """
        return self._url
    
    def __repr__(self) -> str:
        """
        Get a debug representation of the URL.
        
        Returns:
            str: Debug representation
        """
        return f"URL({self._url!r})"
    
    def __eq__(self, other: Any) -> bool:
        """
        Check if two URLs are equal.
        
        Args:
            other: Other URL to compare
            
        Returns:
            bool: True if the URLs are equal
        """
        if isinstance(other, URL):
            return str(self) == str(other)
        elif isinstance(other, str):
            return str(self) == other
        
        return False 