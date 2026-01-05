# SSH Key Setup for TMS Deployment

You've received the `sogo-infra-key.pem` file. Here's how to use it properly.

## Setup SSH Key

### 1. Move and Secure the Key

```bash
# Move the key to .ssh directory
mv ~/Downloads/sogo-infra-key.pem ~/.ssh/

# Set correct permissions (REQUIRED - SSH will refuse to use it otherwise)
chmod 600 ~/.ssh/sogo-infra-key.pem

# Verify permissions
ls -l ~/.ssh/sogo-infra-key.pem
# Should show: -rw------- (only owner can read/write)
```

### 2. Create SSH Config for Easy Access

```bash
# Edit SSH config
nano ~/.ssh/config

# Add these entries:
```

```
# TMS Staging Server
Host tms-staging
    HostName 47.80.66.95
    User root
    IdentityFile ~/.ssh/sogo-infra-key.pem
    ServerAliveInterval 60
    ServerAliveCountMax 3

# TMS Production Server
Host tms-production
    HostName 47.80.71.165
    User root
    IdentityFile ~/.ssh/sogo-infra-key.pem
    ServerAliveInterval 60
    ServerAliveCountMax 3

# Alternative servers (if different)
Host tms-server-1
    HostName 8.220.150.34
    User root
    IdentityFile ~/.ssh/sogo-infra-key.pem

Host tms-server-2
    HostName 8.220.141.16
    User root
    IdentityFile ~/.ssh/sogo-infra-key.pem
```

Save and exit (Ctrl+X, Y, Enter in nano)

### 3. Test Connection

```bash
# Now you can connect easily with:
ssh tms-staging

# Or
ssh tms-production

# Instead of:
ssh -i ~/.ssh/sogo-infra-key.pem root@47.80.66.95
```

## Verify Server Access

```bash
# Connect to staging
ssh tms-staging

# Once connected, check:
hostname
ip addr show eth0
uname -a
df -h
free -h

# Exit
exit
```

## Quick Commands Reference

```bash
# Connect to staging
ssh tms-staging

# Connect to production
ssh tms-production

# Copy files to staging
scp -i ~/.ssh/sogo-infra-key.pem myfile.txt root@47.80.66.95:/tmp/

# Or with SSH config:
scp myfile.txt tms-staging:/tmp/

# Run command on staging without logging in
ssh tms-staging "ls -la /home"

# Multiple commands
ssh tms-staging "cd /home && ls -la && df -h"
```

## Troubleshooting

### "Permission denied (publickey)"

**Fix permissions:**
```bash
chmod 600 ~/.ssh/sogo-infra-key.pem
```

### "WARNING: UNPROTECTED PRIVATE KEY FILE!"

**Fix permissions:**
```bash
chmod 600 ~/.ssh/sogo-infra-key.pem
```

### "Connection refused"

**Check firewall/security group:**
- Alibaba Cloud console → ECS → Security Groups
- Ensure port 22 (SSH) is allowed from your IP

### "Host key verification failed"

**Add to known hosts:**
```bash
ssh-keyscan 47.80.66.95 >> ~/.ssh/known_hosts
ssh-keyscan 47.80.71.165 >> ~/.ssh/known_hosts
```

## Security Best Practices

1. **Never commit the key to git**
   ```bash
   # Add to .gitignore
   echo "*.pem" >> ~/.gitignore_global
   ```

2. **Backup the key securely**
   ```bash
   # Keep a backup in a secure location
   cp ~/.ssh/sogo-infra-key.pem ~/Backups/Keys/
   chmod 600 ~/Backups/Keys/sogo-infra-key.pem
   ```

3. **Use SSH agent for convenience**
   ```bash
   # Add key to SSH agent
   ssh-add ~/.ssh/sogo-infra-key.pem

   # Now you can SSH without specifying key each time
   ssh root@47.80.66.95
   ```

## Next Steps

Now that you have SSH access, you can:

1. **Verify which server is staging/production**
   ```bash
   ssh tms-staging "hostname && ip addr | grep 'inet '"
   ssh tms-production "hostname && ip addr | grep 'inet '"
   ```

2. **Start deployment**
   - Follow: `deployment/QUICK_START.md`
   - Or: `deployment/DEPLOYMENT_CHECKLIST.md`

3. **Check if services are already running**
   ```bash
   ssh tms-staging "systemctl status nginx tms-backend tms-frontend 2>/dev/null || echo 'Services not installed yet'"
   ```
