"""
Test script to decode JWT token from GCGC TMS.
This helps identify the correct NEXTAUTH_SECRET.
"""
import jwt
import sys

# The token from GCGC TMS (you'll need to provide this)
# Get it from: localStorage.getItem('auth_token') in browser after login
token = input("Paste the JWT token from localStorage.getItem('auth_token'): ").strip()

# Try different secrets
secrets = [
    "v1hM2qTu7ckPz8evUzN3EEn0tNUyndttn/sRvkeEl7k=",  # Current server secret
    "krYggXL+KsnsKl0hvE7NqBcTlX2Pq6BwhPsnUUAI4FE=",  # Local .env secret
]

print(f"\nToken preview (first 50 chars): {token[:50]}...\n")

# First, try to decode without verification to see the payload
print("=" * 60)
print("STEP 1: Decoding token WITHOUT verification (to see structure)")
print("=" * 60)
try:
    unverified = jwt.decode(token, options={"verify_signature": False})
    print("✅ Unverified payload:")
    for key, value in unverified.items():
        print(f"  {key}: {value}")
except Exception as e:
    print(f"❌ Failed to decode even without verification: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("STEP 2: Trying to verify with known secrets")
print("=" * 60)

for i, secret in enumerate(secrets, 1):
    print(f"\nAttempt {i}: Testing secret: {secret[:20]}...")
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_signature": True, "verify_exp": False}  # Skip expiry check
        )
        print(f"✅ SUCCESS! Token verified with secret #{i}")
        print("Payload:")
        for key, value in payload.items():
            print(f"  {key}: {value}")
        print(f"\n🎉 Use this NEXTAUTH_SECRET: {secret}")
        sys.exit(0)
    except jwt.InvalidSignatureError:
        print(f"❌ Invalid signature with secret #{i}")
    except Exception as e:
        print(f"❌ Error with secret #{i}: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("STEP 3: Asking GCGC TMS team for NEXTAUTH_SECRET")
print("=" * 60)
print("⚠️  None of the known secrets worked!")
print("You need to ask the GCGC TMS team what NEXTAUTH_SECRET they use.")
print("Or check the GCGC TMS .env file for NEXTAUTH_SECRET value.")
