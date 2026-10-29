# Beta 4 RF setup changes

Radio programming is a required full-page wizard step before Review/Apply and Audio.
Previously saved wizard progress cannot bypass the programming record. Missing records
produce an actionable error; credentials and station settings are preserved.

Optional frequency suggestions select UHF and wide FM; they do not save or program:

- Simplex RX=TX: 438.450, 438.550, 438.675, 445.925, 445.975, 446.025, 446.075, 446.125 MHz.
- Duplex hotspot RX/TX: 433.450/438.450, 433.550/438.550, 433.675/438.675 MHz.
- Custom UHF range: 430.000–449.995 MHz on the existing 2.5 kHz grid.
- 435.000–438.000 MHz, inclusive, is blocked for both RX and TX by frontend and backend.
- 447.000–449.995 MHz shows a possible local-repeater-interference warning; it is not blocked.

These are user-requested application rules, not a statement of permission to operate
at every frequency. Duplex pairs do not add simultaneous TX/RX capability to a SHARI.
VHF limits remain unchanged. Existing tones are kept when choosing a suggestion.

Validation: UI and Python boundary tests pass, including all eleven choices and
hotspot RX/TX ordering. Actual radio programming remains an explicit operator action.
Fresh SD-card and RF acceptance testing remain pending.
