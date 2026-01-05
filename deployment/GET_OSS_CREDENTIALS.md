# How to Get Alibaba Cloud OSS Access Keys

Your OSS bucket `tms-oss-goli` is already created, but you need Access Keys to use it programmatically.

## Method 1: Create RAM User for OSS (Recommended - Most Secure)

This creates a dedicated user with limited permissions (best practice).

### Step 1: Create RAM User

1. Log in to [Alibaba Cloud Console](https://www.alibabacloud.com/)
2. Go to **RAM (Resource Access Management)**
3. Click **Users** → **Create User**
4. Enter details:
   - **Logon Name**: `tms-oss-user`
   - **Display Name**: `TMS OSS Access`
   - Check: **Programmatic Access** (creates AccessKey)
5. Click **OK**

### Step 2: Save Access Keys

⚠️ **IMPORTANT**: The AccessKey Secret is shown only once!

```
AccessKey ID: LTAI******************
AccessKey Secret: ************************
```

**Save these immediately!** You cannot retrieve the secret later.

### Step 3: Grant OSS Permissions

1. Go to **RAM** → **Users**
2. Click on `tms-oss-user`
3. Click **Add Permissions**
4. Select policy: **AliyunOSSFullAccess** (or create custom policy for specific bucket)
5. Click **OK**

### Step 4: Test Access

```bash
# Install ossutil (Alibaba Cloud OSS CLI tool)
wget http://gosspublic.alicdn.com/ossutil/1.7.16/ossutil64
chmod 755 ossutil64

# Configure
./ossutil64 config
# Enter:
# - Endpoint: oss-ap-southeast-6.aliyuncs.com
# - AccessKey ID: <your key>
# - AccessKey Secret: <your secret>

# Test list buckets
./ossutil64 ls
# Should see: oss://tms-oss-goli

# Test upload
echo "test" > test.txt
./ossutil64 cp test.txt oss://tms-oss-goli/test.txt
```

---

## Method 2: Use Root Account Access Keys (Not Recommended)

⚠️ **Security Risk**: Root account keys have full access to everything.

### If you still want to use root account:

1. Log in to [Alibaba Cloud Console](https://www.alibabacloud.com/)
2. Click your account name (top-right)
3. Select **AccessKey Management**
4. Click **Create AccessKey**
5. Complete security verification (SMS/email)
6. **Save the AccessKey ID and Secret immediately**

---

## What to Do After Getting Keys

### Update Backend Environment File

Edit `.env.staging` (or `.env.production`):

```bash
# Replace these placeholder values:
OSS_ACCESS_KEY_ID=your_actual_access_key_id_here
OSS_ACCESS_KEY_SECRET=your_actual_access_key_secret_here

# With your actual keys:
OSS_ACCESS_KEY_ID=LTAI5t******************
OSS_ACCESS_KEY_SECRET=3mK************************
```

### Restart Backend Service

```bash
sudo systemctl restart tms-backend
```

### Test File Upload

Try uploading a file through your TMS application to verify OSS is working.

---

## Security Best Practices

1. ✅ **Use RAM user** instead of root account keys
2. ✅ **Limit permissions** to only OSS (not full account access)
3. ✅ **Rotate keys** regularly (every 90 days)
4. ✅ **Never commit keys** to git (use .env files)
5. ✅ **Use internal endpoint** when accessing from ECS in same region (faster + free bandwidth)

---

## Troubleshooting

### "AccessDenied" error

**Cause**: RAM user doesn't have OSS permissions

**Solution**: Add `AliyunOSSFullAccess` policy to the RAM user

### "InvalidAccessKeyId" error

**Cause**: Wrong AccessKey ID or it was deleted

**Solution**:
1. Verify the key in RAM console
2. Create a new AccessKey if needed

### "SignatureDoesNotMatch" error

**Cause**: Wrong AccessKey Secret

**Solution**: The secret might be copied incorrectly. Create a new AccessKey.

### Connection timeout

**Cause**: Network issue or wrong endpoint

**Solution**:
- Check endpoint matches region: `oss-ap-southeast-6.aliyuncs.com`
- If ECS is in same region, use internal endpoint: `oss-ap-southeast-6-internal.aliyuncs.com`

---

## Quick Reference

```bash
# Your OSS Configuration
Bucket: tms-oss-goli
Region: ap-southeast-6
Public Endpoint: oss-ap-southeast-6.aliyuncs.com
Internal Endpoint: oss-ap-southeast-6-internal.aliyuncs.com (use this for ECS)

# Environment Variables Needed
OSS_ACCESS_KEY_ID=<get from Alibaba Cloud Console>
OSS_ACCESS_KEY_SECRET=<get from Alibaba Cloud Console>
OSS_BUCKET_NAME=tms-oss-goli
OSS_ENDPOINT=oss-ap-southeast-6-internal.aliyuncs.com  # Internal for ECS
```

---

## Need Help?

If you already have AccessKeys but can't find them:
- ⚠️ **AccessKey Secret cannot be retrieved** after creation
- You must **create a new AccessKey** if you lost the secret
- Old keys can be deleted after creating new ones
