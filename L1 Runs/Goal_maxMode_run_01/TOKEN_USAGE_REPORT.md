# Run 01 token usage and time

Stopped at user request. Container exited 137 following Docker stop timeout; monitoring paused. All surviving artifacts remain in this folder.

Model: deepseek/deepseek-flash; thinking: max.

Start: October 16, 2026, 6:12:46 PM EDT.
Stop: October 16, 2026, 9:05:00 PM EDT.
Elapsed container runtime: **2 hours 52 minutes 14.174 seconds** (10,334.174 seconds). Includes model thinking, tool execution and startup/shutdown.

| Token category | Tokens |
|---|---:|
| Total input | 37,859,801 |
| Cached input | 37,754,624 |
| Uncached input | 105,177 |
| Cache writes | 0 |
| Output, including reasoning | 324,424 |
| Reasoning subset of output | 254,344 |
| Non-reasoning output | 70,080 |
| **Total input + output** | **38,184,225** |

177 recorded model responses. Cached context is counted again each time the provider processes it; this is cumulative usage, not unique text size. Reasoning is included in output and must not be added again.

Pi catalog estimated costs: uncached input $0.031553100; cached input $0.226527744; output $0.389308800; **total $0.647389644 USD**. Not verified provider billing.

## Evidence and limitations

Summed assistant usage records in sessions/2026-10-16T22-12-46-574Z_01a146c6-596d-74d3-b53b-ae877e837018.jsonl. Independently summed pi-events.jsonl message_end usage records: all totals and response count match. Docker state supplies start/finish timestamps.

Forced termination prevented normal final data-Pi reports. Unreported in-flight API usage may be missing. These totals exclude Codex management and monitoring usage. No numerical convergence, full design acceptance, CNC qualification or hardware qualification is established by this report.

## Recalculation using published API prices

Source: https://api-docs.deepseek.com/quick_start/pricing/ (checked October16,2026 EDT). Entire run off-peak: Friday22:12 UTC through Saturday01:05 UTC; weekends are off-peak.

Cached input:37,754,624 × $0.003/M = $0.113263872.
Uncached input:105,177 × $0.15/M = $0.015776550.
Output including reasoning:324,424 × $0.60/M = $0.194654400.

**Total at published rates: $0.323694822 USD**, approximately $0.324. This supersedes the Pi catalog estimate for pricing; recorded-usage limitations still apply. Actual account invoice/credits were not checked.
