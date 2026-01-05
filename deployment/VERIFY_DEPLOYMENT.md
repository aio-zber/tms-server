# TMS Deployment Verification Guide

## Quick Health Check

### Staging Environment

```bash
# 1. Check DNS resolution
nslookup tms-chat-staging.example.com
# Should return: 47.80.66.95

# 2. Check HTTPS is working
curl -I https://tms-chat-staging.example.com
# Should return: HTTP/2 200

# 3. Check backend health
curl https://tms-chat-staging.example.com/health
# Should return: {"status": "healthy"}

# 4. Check API health
curl https://tms-chat-staging.example.com/api/v1/health
# Should return API health status

# 5. Check API documentation (staging only)
# Open in browser:
https://tms-chat-staging.example.com/docs
```

### Production Environment

```bash
# 1. Check DNS resolution
nslookup tms-chat.example.com
# Should return: 47.80.71.165

# 2. Check HTTPS is working
curl -I https://tms-chat.example.com
# Should return: HTTP/2 200

# 3. Check backend health
curl https://tms-chat.example.com/health

# 4. Check API health
curl https://tms-chat.example.com/api/v1/health

# 5. Access frontend
# Open in browser:
https://tms-chat.example.com
```

## Detailed Verification Checklist

### ✅ Infrastructure Layer

- [ ] **DNS Resolution**
  ```bash
  dig tms-chat-staging.example.com +short
  # Should show: 47.80.66.95
  ```

- [ ] **SSL Certificate**
  ```bash
  openssl s_client -connect tms-chat-staging.example.com:443 -servername tms-chat-staging.example.com < /dev/null 2>/dev/null | grep -A2 'Certificate chain'
  # Should show Let's Encrypt certificate
  ```

- [ ] **Port Accessibility**
  ```bash
  nc -zv tms-chat-staging.example.com 443
  # Should return: Connection successful
  ```

### ✅ Nginx Layer

- [ ] **Nginx is running**
  ```bash
  ssh root@47.80.66.95 "systemctl status nginx"
  # Should show: active (running)
  ```

- [ ] **Nginx configuration valid**
  ```bash
  ssh root@47.80.66.95 "nginx -t"
  # Should show: syntax is ok
  ```

- [ ] **Check Nginx logs**
  ```bash
  ssh root@47.80.66.95 "tail -n 50 /var/log/nginx/tms-staging-access.log"
  ssh root@47.80.66.95 "tail -n 50 /var/log/nginx/tms-staging-error.log"
  ```

### ✅ Backend Layer (FastAPI)

- [ ] **Backend service running**
  ```bash
  ssh root@47.80.66.95 "systemctl status tms-backend"
  # Should show: active (running)
  ```

- [ ] **Backend listening on port 8000**
  ```bash
  ssh root@47.80.66.95 "netstat -tlnp | grep :8000"
  # Should show uvicorn process
  ```

- [ ] **Backend logs healthy**
  ```bash
  ssh root@47.80.66.95 "journalctl -u tms-backend -n 50"
  # Check for errors
  ```

- [ ] **API endpoints working**
  ```bash
  # Health check
  curl https://tms-chat-staging.example.com/api/v1/health

  # API docs (staging only)
  curl https://tms-chat-staging.example.com/docs
  ```

### ✅ Frontend Layer (Next.js)

- [ ] **Frontend service running**
  ```bash
  ssh root@47.80.66.95 "systemctl status tms-frontend"
  # Should show: active (running)
  ```

- [ ] **Frontend listening on port 3000**
  ```bash
  ssh root@47.80.66.95 "netstat -tlnp | grep :3000"
  # Should show node process
  ```

- [ ] **Frontend logs healthy**
  ```bash
  ssh root@47.80.66.95 "journalctl -u tms-frontend -n 50"
  # Check for errors
  ```

- [ ] **Homepage accessible**
  ```bash
  curl -L https://tms-chat-staging.example.com
  # Should return HTML
  ```

### ✅ Database Layer

- [ ] **Database accessible from ECS**
  ```bash
  ssh root@47.80.66.95 "psql -h localhost -U postgres -d tms_staging_db -c 'SELECT version();'"
  # Should return PostgreSQL version
  ```

- [ ] **Database tables exist**
  ```bash
  ssh root@47.80.66.95 "psql -h localhost -U postgres -d tms_staging_db -c '\dt'"
  # Should show tables: users, conversations, messages, etc.
  ```

### ✅ Redis Layer

- [ ] **Redis accessible from ECS**
  ```bash
  ssh root@47.80.66.95 "redis-cli -h localhost -p 6379 -a REDACTED_REDIS_PASSWORD PING"
  # Should return: PONG
  ```

- [ ] **Redis can set/get**
  ```bash
  ssh root@47.80.66.95 "redis-cli -h localhost -p 6379 -a REDACTED_REDIS_PASSWORD SET test 'hello'"
  ssh root@47.80.66.95 "redis-cli -h localhost -p 6379 -a REDACTED_REDIS_PASSWORD GET test"
  # Should return: hello
  ```

### ✅ OSS Layer (if configured)

- [ ] **OSS accessible**
  ```bash
  # On ECS instance
  ssh root@47.80.66.95
  wget http://gosspublic.alicdn.com/ossutil/1.7.16/ossutil64
  chmod +x ossutil64
  ./ossutil64 config
  ./ossutil64 ls
  # Should show: oss://tms-oss-goli
  ```

### ✅ Application Features

Test these in the browser:

#### Authentication
- [ ] Navigate to: `https://tms-chat-staging.example.com`
- [ ] Should redirect to GCGC login
- [ ] Login with GCGC credentials
- [ ] Should redirect back to TMS chat

#### Messaging
- [ ] Create a new conversation
- [ ] Send a text message
- [ ] Message appears in real-time
- [ ] Check WebSocket connection in browser DevTools

#### File Upload (if OSS configured)
- [ ] Try uploading an image
- [ ] Image should appear in chat
- [ ] Image URL should be from OSS (oss-ap-southeast-6.aliyuncs.com)

#### Real-time Features
- [ ] Open chat in two browsers/tabs
- [ ] Send message in one tab
- [ ] Message appears instantly in other tab (WebSocket working)

## Common Issues & Solutions

### Issue: "Connection refused" or "Cannot reach server"

**Check:**
```bash
# Is DNS resolving?
nslookup tms-chat-staging.example.com

# Is firewall allowing connections?
ssh root@47.80.66.95 "ufw status"

# Are services running?
ssh root@47.80.66.95 "systemctl status nginx tms-backend tms-frontend"
```

**Fix:**
```bash
# Enable firewall ports
ssh root@47.80.66.95 "ufw allow 80/tcp && ufw allow 443/tcp"

# Restart services
ssh root@47.80.66.95 "systemctl restart nginx tms-backend tms-frontend"
```

### Issue: "SSL certificate error" or "Not secure"

**Check:**
```bash
# Is SSL certificate valid?
openssl s_client -connect tms-chat-staging.example.com:443 -servername tms-chat-staging.example.com < /dev/null 2>/dev/null | openssl x509 -noout -dates
```

**Fix:**
```bash
# Renew SSL certificate
ssh root@47.80.66.95 "certbot renew --force-renewal"
ssh root@47.80.66.95 "systemctl restart nginx"
```

### Issue: "502 Bad Gateway"

**Meaning:** Nginx can't reach backend/frontend

**Check:**
```bash
# Are backend/frontend running?
ssh root@47.80.66.95 "systemctl status tms-backend tms-frontend"

# Check logs
ssh root@47.80.66.95 "journalctl -u tms-backend -n 50"
ssh root@47.80.66.95 "journalctl -u tms-frontend -n 50"
```

**Fix:**
```bash
# Restart services
ssh root@47.80.66.95 "systemctl restart tms-backend tms-frontend"
```

### Issue: "504 Gateway Timeout"

**Meaning:** Backend is taking too long to respond

**Check:**
```bash
# Check backend logs for slow queries
ssh root@47.80.66.95 "journalctl -u tms-backend -n 100"

# Check database connection
ssh root@47.80.66.95 "psql -h localhost -U postgres -d tms_staging_db -c 'SELECT COUNT(*) FROM pg_stat_activity;'"
```

### Issue: "Login redirects but fails"

**Check:**
```bash
# JWT_SECRET must match GCGC
grep JWT_SECRET /home/tmsapp/tms-server/.env.staging
grep NEXTAUTH_SECRET /home/tmsapp/tms-client/.env.production.local

# Should be identical to GCGC's NEXTAUTH_SECRET
```

### Issue: "WebSocket connection fails"

**Check:**
```bash
# Test WebSocket endpoint
wscat -c wss://tms-chat-staging.example.com/ws

# Check Nginx WebSocket configuration
ssh root@47.80.66.95 "grep -A 10 'location /ws/' /etc/nginx/sites-available/tms-staging"
```

### Issue: "File uploads fail"

**Check:**
```bash
# OSS credentials configured?
ssh root@47.80.66.95 "grep OSS_ACCESS_KEY /home/tmsapp/tms-server/.env.staging"

# Test OSS access
ssh root@47.80.66.95 "cd /home/tmsapp && ./ossutil64 ls oss://tms-oss-goli"
```

## Performance Checks

### Response Time
```bash
# Measure response time
curl -w "@-" -o /dev/null -s https://tms-chat-staging.example.com <<'EOF'
    time_namelookup:  %{time_namelookup}s\n
       time_connect:  %{time_connect}s\n
    time_appconnect:  %{time_appconnect}s\n
      time_redirect:  %{time_redirect}s\n
   time_starttransfer:  %{time_starttransfer}s\n
       time_total:  %{time_total}s\n
EOF

# Should be < 1 second for total time
```

### Concurrent Connections
```bash
# Check active connections
ssh root@47.80.66.95 "netstat -an | grep :443 | wc -l"
```

### Resource Usage
```bash
# CPU and Memory
ssh root@47.80.66.95 "top -b -n 1 | head -20"

# Disk space
ssh root@47.80.66.95 "df -h"
```

## Monitoring Commands

### Real-time Logs
```bash
# Watch all logs at once
ssh root@47.80.66.95 "tail -f /var/log/nginx/tms-staging-*.log & journalctl -u tms-backend -f & journalctl -u tms-frontend -f"
```

### Service Status Dashboard
```bash
# Quick status check
ssh root@47.80.66.95 "systemctl status nginx tms-backend tms-frontend --no-pager"
```

## Browser Testing

### DevTools Checks

1. **Network Tab**
   - API calls should return 200 OK
   - WebSocket shows "101 Switching Protocols"
   - Static files loaded from CDN (if configured)

2. **Console Tab**
   - No JavaScript errors
   - WebSocket connection established
   - No CORS errors

3. **Application Tab**
   - Session storage has auth token
   - Cookies set correctly

### Lighthouse Audit

Run Google Lighthouse for:
- Performance score
- Accessibility
- Best practices
- SEO

## Success Criteria

Your deployment is successful when:

✅ All URLs return HTTP 200:
- `https://tms-chat-staging.example.com`
- `https://tms-chat-staging.example.com/api/v1/health`
- `https://tms-chat-staging.example.com/docs` (staging)

✅ All services running:
- nginx: active (running)
- tms-backend: active (running)
- tms-frontend: active (running)

✅ SSL certificate valid:
- Issued by Let's Encrypt
- Expires in 90 days

✅ Database connected:
- Can query tables
- Migrations applied

✅ Redis connected:
- PING returns PONG
- Can SET/GET values

✅ Application features working:
- Login/authentication
- Send messages
- Real-time updates
- File uploads (if OSS configured)

## Next Steps After Verification

1. **Set up monitoring**
   - Alibaba Cloud CloudMonitor
   - Custom alerts for downtime

2. **Configure backups**
   - Database backups running daily
   - Test restore procedure

3. **Performance tuning**
   - Enable Nginx caching
   - Optimize database queries
   - Configure CDN for static assets

4. **Security hardening**
   - Regular security updates
   - Firewall rules
   - Rate limiting

5. **Documentation**
   - Document any custom configurations
   - Update runbooks for common issues

Congratulations on your deployment! 🎉
