"""Opt-in same-origin policy for ALLMODE's loopback HTTPS reverse proxy."""
import ipaddress
import json
import subprocess
from urllib.parse import urlsplit


def local_ipv4_addresses():
    """Read current kernel addresses, including secondary IPv4 addresses."""
    result = subprocess.run(['ip', '-j', '-4', 'address', 'show'],
                            capture_output=True, text=True, check=True, timeout=2)
    addresses = set()
    interfaces = json.loads(result.stdout)
    if not isinstance(interfaces, list):
        raise ValueError('Invalid interface data')
    for interface in interfaces:
        if not isinstance(interface, dict) or not isinstance(interface.get('addr_info', []), list):
            raise ValueError('Invalid interface data')
        for address in interface.get('addr_info', []):
            if not isinstance(address, dict):
                raise ValueError('Invalid interface address')
            if address.get('family') == 'inet':
                addresses.add(str(ipaddress.IPv4Address(address['local'])))
    return addresses


def authority(value):
    """Accept one unambiguous HTTPS authority, with default port only."""
    if not value or any(c.isspace() for c in value) or any(c in value for c in '/\\?#@,%'):
        return None
    try:
        parsed = urlsplit('https://' + value)
        if parsed.port not in (None, 443) or not parsed.hostname:
            return None
        host = parsed.hostname.lower()
        if ':' in host:  # Appliance nginx currently listens on IPv4 only.
            return None
        if any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789.-' for c in host):
            return None
        return host
    except ValueError:
        return None


def allowed(handler, configured_origins, addresses=None):
    """Require trusted TLS proxy, allowed destination, and same request origin.

    Configured numeric IPs are intentionally not trusted: DHCP may have moved.
    The nginx location must overwrite Host and X-Forwarded-Proto, and the
    application must remain bound to loopback as it is in the installer.
    """
    try:
        if not ipaddress.ip_address(handler.client_address[0]).is_loopback:
            return False
    except ValueError:
        return False
    for key in ('Host', 'Origin', 'X-Forwarded-Proto'):
        if len(handler.headers.get_all(key, [])) != 1:
            return False
    if handler.headers['X-Forwarded-Proto'] != 'https':
        return False
    host = authority(handler.headers['Host'])
    origin = handler.headers['Origin']
    if not host or not origin.startswith('https://'):
        return False
    if authority(origin[len('https://'):]) != host:
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        names = set()
        for item in (configured_origins or '').split(','):
            if item.startswith('https://'):
                name = authority(item[len('https://'):])
                if name:
                    names.add(name)
        return host in names
    if address.version != 4 or address.is_unspecified or address.is_multicast:
        return False
    try:
        return str(address) in (local_ipv4_addresses() if addresses is None else addresses)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False
