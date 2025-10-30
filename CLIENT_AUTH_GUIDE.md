# TMS Client Authentication Guide

**Fix for CORS Error: "Access-Control-Allow-Origin header is not present"**

This guide explains how to fix the authentication flow in the TMS Client to eliminate CORS errors and establish proper communication with the TMS Server.

---

## ❌ The Problem

**Current Error:**
```
Access to fetch at 'https://gcgc-team-management-system-staging.up.railway.app/auth/signin'
from origin 'https://tms-client-staging.up.railway.app'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header
```

**Root Cause:**
The TMS Client is calling GCGC's API directly from the browser, which is incorrect architecture. GCGC is the **user management system**, not the **messaging backend**.

**Wrong Flow (Current):**
```
TMS Client → GCGC API directly → ❌ CORS Error
```

**Correct Flow:**
```
TMS Client → TMS Server → GCGC API (server-to-server) → ✅ Works
```

---

## ✅ The Solution

### Architecture Overview

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  TMS Client  │         │  TMS Server  │         │     GCGC     │
│  (Browser)   │         │  (Backend)   │         │ (User Mgmt)  │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       │ 1. Auth with GCGC ─────────────────────────────>│
       │    (OAuth/NextAuth)    │                        │
       │<───────────────────────────────────────────────│
       │ 2. Get JWT token       │                        │
       │                        │                        │
       │ 3. Send to TMS Server ─>│                        │
       │    POST /api/v1/auth/login                     │
       │                        │                        │
       │                        │ 4. Validate JWT        │
       │                        │    (local decode)      │
       │                        │                        │
       │                        │ 5. Sync user ──────────>│
       │                        │    (API key)           │
       │                        │<───────────────────────│
       │                        │                        │
       │ 6. Return profile <────│                        │
       │                        │                        │
       │ 7. All API calls ──────>│                        │
       │    with JWT token      │                        │
```

---

## 🔧 Implementation Steps

### Step 1: Update Environment Variables

Add these to your `.env` file:

```bash
# TMS Server URL (messaging backend)
NEXT_PUBLIC_TMS_SERVER_URL=https://tms-server-staging.up.railway.app

# GCGC URL (user management - for authentication only)
NEXT_PUBLIC_GCGC_URL=https://gcgc-team-management-system-staging.up.railway.app
```

### Step 2: Fix Authentication Service

**File: `src/services/auth.service.ts`** (or similar)

```typescript
// ❌ REMOVE THIS - Don't call GCGC API directly
async function getCurrentUser() {
  const response = await fetch(
    'https://gcgc-team-management-system-staging.up.railway.app/api/v1/users/me',
    { credentials: 'include' }  // ❌ WRONG
  );
  return response.json();
}

// ✅ ADD THIS - Call TMS Server instead
async function validateTokenWithTMS(jwtToken: string) {
  const response = await fetch(
    `${process.env.NEXT_PUBLIC_TMS_SERVER_URL}/api/v1/auth/login`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ token: jwtToken })
    }
  );

  if (!response.ok) {
    throw new Error('TMS authentication failed');
  }

  const data = await response.json();
  return data.user;
}
```

### Step 3: Update Login Flow

**File: `src/app/login/page.tsx`** (or similar)

```typescript
'use client';

import { signIn, useSession } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function LoginPage() {
  const router = useRouter();
  const { data: session, status } = useSession();

  useEffect(() => {
    if (status === 'authenticated' && session?.accessToken) {
      // User is authenticated with GCGC, now validate with TMS Server
      validateWithTMS(session.accessToken);
    }
  }, [status, session]);

  async function validateWithTMS(jwtToken: string) {
    try {
      // Send token to TMS Server for validation and user sync
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_TMS_SERVER_URL}/api/v1/auth/login`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ token: jwtToken })
        }
      );

      if (!response.ok) {
        throw new Error('TMS authentication failed');
      }

      const { user } = await response.json();

      // Store JWT and user for subsequent API calls
      localStorage.setItem('tms_jwt', jwtToken);
      localStorage.setItem('tms_user', JSON.stringify(user));

      // Redirect to app
      router.push('/');
    } catch (error) {
      console.error('TMS authentication error:', error);
      // Handle error (show message, clear session, etc.)
    }
  }

  function handleLogin() {
    // Redirect to GCGC for authentication
    signIn('credentials', {
      callbackUrl: window.location.origin + '/login'
    });
  }

  return (
    <div>
      <h1>TMS Login</h1>
      <button onClick={handleLogin}>
        Login with GCGC
      </button>
    </div>
  );
}
```

### Step 4: Update API Client

**File: `src/lib/apiClient.ts`** (or similar)

```typescript
const TMS_SERVER_URL = process.env.NEXT_PUBLIC_TMS_SERVER_URL;

class ApiClient {
  private getAuthToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('tms_jwt');
  }

  async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getAuthToken();

    if (!token) {
      // Redirect to login if no token
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw new Error('Not authenticated');
    }

    const response = await fetch(`${TMS_SERVER_URL}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    // Handle token expiration
    if (response.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('tms_jwt');
        localStorage.removeItem('tms_user');
        window.location.href = '/login';
      }
      throw new Error('Authentication expired');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'API request failed');
    }

    return response.json();
  }

  // Message API
  async getMessages(conversationId: string, params?: { limit?: number; cursor?: string }) {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.request(
      `/api/v1/messages/conversations/${conversationId}/messages?${queryParams}`
    );
  }

  // Conversation API
  async getConversations(params?: { limit?: number; cursor?: string }) {
    const queryParams = new URLSearchParams(params as any).toString();
    return this.request(`/api/v1/conversations?${queryParams}`);
  }

  // Search API
  async searchMessages(data: { query: string; conversation_id?: string; limit?: number }) {
    return this.request('/api/v1/messages/search', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  // User API
  async getCurrentUser() {
    return this.request('/api/v1/users/me');
  }
}

export const apiClient = new ApiClient();
```

### Step 5: Update NextAuth Configuration

**File: `src/app/api/auth/[...nextauth]/route.ts`**

```typescript
import NextAuth from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';

const handler = NextAuth({
  providers: [
    CredentialsProvider({
      name: 'GCGC',
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" }
      },
      async authorize(credentials) {
        // Authenticate with GCGC
        const res = await fetch(
          `${process.env.GCGC_URL}/api/auth/signin`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(credentials)
          }
        );

        const user = await res.json();

        if (res.ok && user) {
          return user;
        }
        return null;
      }
    })
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        // Add access token to JWT
        token.accessToken = user.accessToken;
      }
      return token;
    },
    async session({ session, token }) {
      // Add access token to session
      session.accessToken = token.accessToken;
      return session;
    }
  },
  pages: {
    signIn: '/login'
  }
});

export { handler as GET, handler as POST };
```

---

## 🧪 Testing the Fix

### 1. Test Login Flow

```bash
# Start the client
npm run dev

# Navigate to http://localhost:3000/login
# Click "Login with GCGC"
# Enter credentials
# Should redirect back and call TMS Server
# Check browser console for any errors
```

### 2. Test API Calls

```typescript
// In browser console after login:
const token = localStorage.getItem('tms_jwt');
console.log('JWT Token:', token);

// Test API call
fetch('https://tms-server-staging.up.railway.app/api/v1/conversations', {
  headers: {
    'Authorization': `Bearer ${token}`
  }
})
.then(res => res.json())
.then(data => console.log('Conversations:', data));
```

### 3. Verify No CORS Errors

Check browser console - you should see:
- ✅ No CORS errors
- ✅ Successful API responses from TMS Server
- ✅ JWT token in localStorage
- ✅ User data in localStorage

---

## 📋 Checklist

- [ ] Remove all direct calls to GCGC API from client code
- [ ] Add TMS Server URL to environment variables
- [ ] Update authentication service to call TMS Server
- [ ] Update login flow to validate with TMS Server
- [ ] Update API client to use TMS Server
- [ ] Store JWT token in localStorage
- [ ] Include JWT token in all API requests
- [ ] Test login flow end-to-end
- [ ] Verify no CORS errors in browser console
- [ ] Test message sending/receiving
- [ ] Test conversation loading

---

## 🔍 Debugging Tips

### If you see CORS errors:

1. **Check which URL is being called**
   - ✅ Should be: `https://tms-server-staging.up.railway.app`
   - ❌ Should NOT be: `https://gcgc-team-management-system-staging.up.railway.app`

2. **Check browser Network tab**
   - Look for failed requests
   - Check request headers (should include `Authorization: Bearer <token>`)
   - Check response headers (should include CORS headers)

3. **Check JWT token**
   ```javascript
   const token = localStorage.getItem('tms_jwt');
   console.log('Token exists:', !!token);
   console.log('Token:', token);
   ```

4. **Test TMS Server directly**
   ```bash
   curl -X POST https://tms-server-staging.up.railway.app/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"token": "YOUR_JWT_TOKEN"}'
   ```

### Common Mistakes:

1. **Calling wrong API** - Client should call TMS Server, not GCGC
2. **Missing Authorization header** - All TMS Server requests need JWT token
3. **Wrong environment variable** - Use `NEXT_PUBLIC_TMS_SERVER_URL`
4. **Not storing JWT** - Save JWT token after GCGC authentication
5. **Using credentials: 'include'** - Don't use cookies, use Authorization header

---

## 📞 Support

If you encounter issues:

1. Check browser console for errors
2. Check Network tab for failed requests
3. Verify environment variables are set correctly
4. Ensure TMS Server is running and accessible
5. Contact backend team with error logs

---

## ✅ Success Criteria

After implementing these changes:

1. ✅ No CORS errors in browser console
2. ✅ Login flow redirects to GCGC and back successfully
3. ✅ JWT token is stored in localStorage
4. ✅ API calls to TMS Server succeed (200 OK)
5. ✅ Messages load and display correctly
6. ✅ Real-time messaging works via WebSocket

---

**Last Updated:** 2025-01-23
**TMS Server Version:** 1.0.3
**Status:** Ready for Implementation
