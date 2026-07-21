# Authentication and session validation

## Result

The local UniFi OS login, logout, session-cookie name, CSRF source, unauthenticated status, and an authenticated Device read were observed in the real UniFi Network web interface.

| Item | Confirmed observation |
|---|---|
| Login | `POST /api/auth/login` |
| Login status | HTTP 200 |
| Request field names | `password`, `rememberMe`, `token`, `username` |
| Login response | authenticated user-profile object |
| Session cookie name | `TOKEN` |
| CSRF header | `X-CSRF-Token` |
| CSRF source | response header |
| Authenticated Device read | `GET /proxy/network/api/s/site_001/stat/device`, HTTP 200 |
| Logout | `POST /api/auth/logout`, HTTP 200, empty body |
| Unauthenticated observation | `GET /api/users/self`, HTTP 401 |

The browser reached the authenticated Network view without an MFA challenge or CAPTCHA. No certificate warning reappeared during the login.

## Login request and response contract

Only request field names were retained. The complete request body was discarded. The response was recorded only as a top-level object representing the authenticated user profile. Token-bearing, identity, profile, and authorization fields were omitted.

The `Set-Cookie` response header established the cookie named `TOKEN`. Only that name is retained. Cookie values and all other session values were discarded.

## CSRF contract

`X-CSRF-Token` was observed as a controller response header, including on the confirmed read-only Network-version response after authentication. The integration may retain the current value only in memory and may send it only under the same header name when a confirmed write requires CSRF protection.

The token value was neither retained nor compared across sessions. Therefore value-level rotation is not claimed; only availability after successful authentication is confirmed.

## Session failure policy

The signed-out UI produced HTTP 401 for `GET /api/users/self`. HTTP 403 was not observed as a session-expiry response. Productive code must nevertheless handle 401 and 403 conservatively:

- A read may authenticate once and repeat that read once.
- A write must never be repeated automatically after an ambiguous authentication or transport failure.
- After a write-side 401 or 403, the client must authenticate, read the current Device state, and classify the outcome.

No artificial invalid-login sequence, lockout, or forced expiration was attempted.

## Security validation

- No credential value, Cookie value, session value, CSRF value, API key, JWT, address, hardware address, internal name, or raw request was written to the project.
- The complete login payload and user-profile response were not stored.
- No alternate login, logout, or session endpoint was tried.
- All observed requests were caused by the real browser UI.
- The Chrome session was not deliberately terminated after validation.

**Authentication/session contract: confirmed for the captured UniFi OS environment.**
