# Security Measures

This document outlines the security measures implemented in NoteKeep to prevent injection attacks and other vulnerabilities.

## Input Validation & Sanitization

### Telegram Bot (`telegram_poller.py`)

#### Message Input
- **Length limit**: Messages limited to 4000 characters
- **Control characters**: Removed from user-provided text
- **URL limit**: Maximum 10 URLs per message

#### URL Validation
- **Scheme validation**: Only `http://` and `https://` allowed
- **Domain validation**: Must have valid domain (min 3 chars)
- **Length limit**: URLs limited to 2048 characters
- **SSRF protection**: Blocks localhost, private IPs (10.x, 172.16-31.x, 192.168.x)
- **Malformed URLs**: Rejected during parsing

#### Metadata Fetching
- **Response size limit**: 5MB maximum to prevent memory exhaustion
- **Timeout**: 10 seconds with max 3 redirects
- **Connection limit**: Max 5 concurrent connections
- **Title sanitization**: Limited to 500 characters, HTML special chars escaped
- **Domain sanitization**: Only alphanumeric, dots, and hyphens allowed (max 100 chars)
- **Keywords sanitization**: Only alphanumeric, spaces, hyphens (max 50 chars each, max 5 keywords)

#### Output Sanitization
- **HTML escaping**: All user content escaped for Telegram HTML mode (`&`, `<`, `>`)
- **Display limits**: Titles limited to 200 chars in messages, tags to 5

### Pydantic Schemas (`schemas.py`)

#### LinkCreate Validation
- **URL**: Validated by Pydantic's `HttpUrl` type (ensures valid HTTP/HTTPS URL)
- **Title**: Max 500 characters, stripped whitespace, min 1 char if provided
- **Notes**: Max 10,000 characters, stripped whitespace
- **Tags**: 
  - Maximum 10 tags per link
  - Each tag: 2-100 characters
  - Only valid string values accepted
- **Collection**: 2-100 characters if provided

### Database Layer (`crud.py`)

#### SQL Injection Protection
- **SQLAlchemy ORM**: All queries use parameterized statements (prevents SQL injection)
- **No raw SQL**: All database operations use ORM methods
- **Type safety**: Pydantic validates all inputs before database operations

## Attack Prevention

### Cross-Site Scripting (XSS)
- ✅ All user input sanitized before storage
- ✅ HTML special characters escaped in Telegram messages
- ✅ Jinja2 templates auto-escape by default (web UI)

### SQL Injection
- ✅ SQLAlchemy ORM with parameterized queries
- ✅ No string concatenation in queries
- ✅ Type validation via Pydantic

### Server-Side Request Forgery (SSRF)
- ✅ Blocked localhost and private IP ranges
- ✅ Only HTTP/HTTPS schemes allowed
- ✅ Response size limits prevent resource exhaustion
- ✅ Connection limits and timeouts

### Denial of Service (DoS)
- ✅ Message length limits (4000 chars)
- ✅ URL count limits (max 10 per message)
- ✅ Response size limits (5MB)
- ✅ Connection timeouts (10 seconds)
- ✅ Tag limits (max 10 per link)
- ✅ Title/notes length limits

### Path Traversal
- ✅ No file system operations based on user input
- ✅ Static files served from fixed directory

### Command Injection
- ✅ No shell commands executed with user input
- ✅ No subprocess calls with user data

## Security Best Practices

### Environment Variables
- ✅ Sensitive data (tokens) in `.env` file
- ✅ `.env` excluded from git (`.gitignore`)
- ✅ `.env` excluded from Copilot (`.copilotignore`)

### Dependencies
- ✅ All dependencies pinned with minimum versions
- ✅ Regular updates recommended for security patches

### Docker
- ✅ Non-root user should be used (recommended to add)
- ✅ Minimal base image (python:3.11-slim)
- ✅ Environment variables for configuration

## Recommendations for Production

### Additional Security Measures

1. **Rate Limiting**
   - Implement per-user rate limiting for bot messages
   - Consider Redis for distributed rate limiting

2. **User Authentication**
   - Add whitelist of allowed Telegram user IDs
   - Reject messages from unauthorized users

3. **Logging & Monitoring**
   - Log all bot interactions
   - Monitor for suspicious patterns
   - Set up alerts for unusual activity

4. **HTTPS**
   - Use HTTPS for web interface
   - Valid SSL/TLS certificate

5. **Database**
   - Regular backups
   - File permissions (600) for SQLite file
   - Consider PostgreSQL for production

6. **Content Security Policy**
   - Add CSP headers to web interface
   - Restrict inline scripts

7. **Bot Token Security**
   - Rotate token periodically
   - Use different tokens for dev/prod
   - Never commit tokens to git

### Example: User Whitelist

Add to `.env`:
```bash
TELEGRAM_ALLOWED_USERS=123456789,987654321
```

Update `telegram_poller.py`:
```python
ALLOWED_USERS = [int(x) for x in settings.telegram_allowed_users.split(",")] if settings.telegram_allowed_users else []

async def process_message(message: dict[str, Any]) -> None:
    chat_id = message["chat"]["id"]
    
    # Check whitelist
    if ALLOWED_USERS and chat_id not in ALLOWED_USERS:
        await send_telegram_message(chat_id, "❌ Unauthorized user")
        return
    
    # ... rest of processing
```

## Security Checklist

- [x] Input validation (length, format, type)
- [x] Output sanitization (HTML escaping)
- [x] SQL injection prevention (ORM)
- [x] XSS prevention (escaping)
- [x] SSRF prevention (IP blocking)
- [x] DoS prevention (rate limits, size limits)
- [x] Sensitive data protection (.env, .gitignore)
- [x] Pydantic validation (types, constraints)
- [ ] User authentication/whitelist (recommended)
- [ ] Rate limiting (recommended)
- [ ] Logging & monitoring (recommended)
- [ ] HTTPS (recommended for production)

## Vulnerability Disclosure

If you discover a security vulnerability, please email the maintainer or open a private security advisory on GitHub.
