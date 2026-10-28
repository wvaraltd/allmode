# DHCP login fix verification

October 28, 2026: 109 application tests passed for the fixed beta package, including 12 origin policy, real HTTP and installer regressions. Archive contents/checksums and TAR/ZIP parity were verified; Python and shell syntax passed. Native codecs were not rebuilt for this patch, and fresh-card/RF acceptance remains pending.

The working Pi received only the four targeted server hunks and new helper, preserving its existing customized application rather than replacing it with beta 2/3. Its current-IP and stable-hostname requests reached the login parser, while missing, hostile and old-IP origins were rejected. GET /login returned 200 and HTTP redirected to the current destination IP. Radio process IDs were unchanged. This did not verify a password login or RF/audio operation. The existing self-signed certificate and its original IP SAN were unchanged; certificate renewal/trust is separate.
