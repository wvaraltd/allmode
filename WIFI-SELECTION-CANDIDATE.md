# Stable Wi-Fi selection candidate

Based on stable core-3 source 645a39e. No experimental DVSwitch integration.
This candidate is not an authorization to switch either test station's network.

## Operator flow

Scan lists selectable network names. Identical name/security results are grouped
with the strongest reported signal and access-point count; different security
variants remain separate. Selection fills the form and clears the old password,
but never saves or connects. The Connect button is always visible.

Connect requires valid fields and an explicit warning that the browser may lose
connectivity and the saved profile will reconnect automatically. Save without
connecting remains available. Hidden networks can be entered manually. Cancel,
selection/security changes and submission clear the password. No password is put
in browser storage, command-line arguments or diagnostic messages. Repeated
pending requests and unchanged successfully scheduled submissions are suppressed.

Supported form security: WPA/WPA2 Personal (including WPA2/WPA3 transition results)
and explicitly selected open networks, with an unencrypted-network warning.
Enterprise/802.1X, WEP, WPA3-only and unknown scan security are marked unsupported;
the UI does not silently downgrade them. Existing profiles are not deleted.

Backend preflights required tools before profile creation for direct Connect.
Scheduling is not proof of successful association, DHCP, DNS or Internet access.
Errors after a write distinguish saved profiles from unconfirmed connection
scheduling. No automatic retry or automatic NetworkManager installation/start.

## Validation boundary

All automated network writes, scheduler invocations and Asterisk operations are
mocked. Synthetic SSIDs only. No real Wi-Fi switch, AP activation, RF operation or
password capture was performed. Actual browser rendering and controlled physical
network commissioning are separate acceptance checks.

## Setup access point: design only

No setup AP is enabled or implemented by this patch. A future opt-in setup AP
would need board/interface capability checks, a unique authenticated setup
session, explicit timeout/exit, recovery to the original network configuration,
and protection against exposing station administration publicly. A single
wireless interface may not support concurrent client/AP use reliably; do not
silently convert an operating station into an access point. Existing-node
connectivity and user choice must take precedence over convenience.
