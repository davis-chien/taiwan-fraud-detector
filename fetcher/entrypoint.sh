#!/bin/sh
# Apply network-level egress policy before starting the fetcher worker.
#
# This is defense-in-depth on top of the application-level SSRF checks in
# scraper.py, unshortener.py, and validator.py. A bug in the application layer
# cannot bypass a network-level DROP rule.
#
# Requires NET_ADMIN capability (docker-compose.yml: cap_add: [NET_ADMIN]).
# Fails gracefully if iptables is unavailable (e.g. Hugging Face Spaces).

set -e

apply_egress_policy() {
    # 1. Allow loopback — Docker's embedded DNS is at 127.0.0.11; healthcheck
    #    uses localhost:8080.
    iptables -A OUTPUT -o lo -j ACCEPT

    # 2. Allow established/related — response packets for connections we opened.
    iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
    iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

    # 3. Allow DNS before private-IP blocks — the resolver may be at a private
    #    address (host-configured or Docker-internal).
    iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

    # 4. Block cloud metadata endpoints (AWS/GCP/Azure/link-local).
    iptables -A OUTPUT -d 169.254.0.0/16 -j REJECT

    # 5. Block RFC 1918 private ranges.
    iptables -A OUTPUT -d 10.0.0.0/8 -j REJECT
    iptables -A OUTPUT -d 172.16.0.0/12 -j REJECT
    iptables -A OUTPUT -d 192.168.0.0/16 -j REJECT

    # 6. Allow WHOIS (port 43) and HTTP/HTTPS outbound — public IPs only at
    #    this point since private ranges were rejected above.
    iptables -A OUTPUT -p tcp --dport 43  -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 80  -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT

    # 7. Drop everything else outbound.
    iptables -A OUTPUT -j DROP
}

if command -v iptables > /dev/null 2>&1; then
    if apply_egress_policy 2>/dev/null; then
        echo "[fetcher] egress policy applied: blocks metadata + private IPs, allows DNS/WHOIS/HTTP/HTTPS"
    else
        echo "[fetcher] egress policy partially applied or skipped — application-level SSRF checks remain active"
    fi
else
    echo "[fetcher] iptables not found — application-level SSRF checks remain active"
fi

exec "$@"
