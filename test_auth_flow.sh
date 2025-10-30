#!/bin/bash

# TMS Server Authentication Flow Test Script
# This script tests the authentication endpoints to verify CORS and JWT validation

echo "🧪 TMS Server Authentication Flow Test"
echo "========================================"
echo ""

# Configuration
TMS_SERVER_URL="https://tms-server-staging.up.railway.app"
CLIENT_ORIGIN="https://tms-client-staging.up.railway.app"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📍 Test Configuration:"
echo "   TMS Server: $TMS_SERVER_URL"
echo "   Client Origin: $CLIENT_ORIGIN"
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "--------------------"
response=$(curl -s -w "\n%{http_code}" "$TMS_SERVER_URL/health")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC} - Server is healthy"
    echo "   Response: $body"
else
    echo -e "${RED}❌ FAIL${NC} - Server health check failed (HTTP $http_code)"
    echo "   Response: $body"
fi
echo ""

# Test 2: CORS Preflight (OPTIONS)
echo "Test 2: CORS Preflight Request"
echo "------------------------------"
response=$(curl -s -w "\n%{http_code}" \
  -X OPTIONS \
  -H "Origin: $CLIENT_ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type,Authorization" \
  "$TMS_SERVER_URL/api/v1/auth/login")

http_code=$(echo "$response" | tail -n1)
headers=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC} - CORS preflight successful"

    # Check for CORS headers
    if echo "$headers" | grep -q "access-control-allow-origin"; then
        echo -e "   ${GREEN}✅${NC} Access-Control-Allow-Origin header present"
    else
        echo -e "   ${RED}❌${NC} Access-Control-Allow-Origin header missing"
    fi

    if echo "$headers" | grep -q "access-control-allow-methods"; then
        echo -e "   ${GREEN}✅${NC} Access-Control-Allow-Methods header present"
    else
        echo -e "   ${RED}❌${NC} Access-Control-Allow-Methods header missing"
    fi
else
    echo -e "${RED}❌ FAIL${NC} - CORS preflight failed (HTTP $http_code)"
fi
echo ""

# Test 3: Login with Invalid Token (should fail gracefully)
echo "Test 3: Login with Invalid Token"
echo "--------------------------------"
response=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Origin: $CLIENT_ORIGIN" \
  -H "Content-Type: application/json" \
  -d '{"token": "invalid_token"}' \
  "$TMS_SERVER_URL/api/v1/auth/login")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "401" ]; then
    echo -e "${GREEN}✅ PASS${NC} - Invalid token rejected correctly (HTTP 401)"
    echo "   Response: $body"

    # Check if response has enhanced error format
    if echo "$body" | grep -q "error"; then
        echo -e "   ${GREEN}✅${NC} Enhanced error message format present"
    fi
else
    echo -e "${YELLOW}⚠️  WARN${NC} - Expected HTTP 401, got HTTP $http_code"
    echo "   Response: $body"
fi
echo ""

# Test 4: Token Validation Endpoint
echo "Test 4: Token Validation Endpoint"
echo "---------------------------------"
response=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Origin: $CLIENT_ORIGIN" \
  -H "Content-Type: application/json" \
  -d '{"token": "invalid_token"}' \
  "$TMS_SERVER_URL/api/v1/auth/validate")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC} - Validation endpoint accessible"
    echo "   Response: $body"

    # Check if response has valid field
    if echo "$body" | grep -q '"valid":false'; then
        echo -e "   ${GREEN}✅${NC} Invalid token detected correctly"
    fi
else
    echo -e "${RED}❌ FAIL${NC} - Validation endpoint failed (HTTP $http_code)"
    echo "   Response: $body"
fi
echo ""

# Test 5: CORS Headers in Error Responses
echo "Test 5: CORS Headers in Error Responses"
echo "---------------------------------------"
response=$(curl -s -i -X POST \
  -H "Origin: $CLIENT_ORIGIN" \
  -H "Content-Type: application/json" \
  -d '{"token": "invalid"}' \
  "$TMS_SERVER_URL/api/v1/auth/login" 2>&1)

if echo "$response" | grep -iq "access-control-allow-origin"; then
    echo -e "${GREEN}✅ PASS${NC} - CORS headers present in error response"
    echo "$response" | grep -i "access-control" | sed 's/^/   /'
else
    echo -e "${RED}❌ FAIL${NC} - CORS headers missing in error response"
fi
echo ""

# Summary
echo "📊 Test Summary"
echo "==============="
echo ""
echo "If all tests pass, the server is ready for client integration."
echo ""
echo "Next steps:"
echo "1. Verify ALLOWED_ORIGINS environment variable includes:"
echo "   $CLIENT_ORIGIN"
echo ""
echo "2. Update client code to call TMS Server instead of GCGC"
echo "   See: CLIENT_AUTH_GUIDE.md"
echo ""
echo "3. Test with a real JWT token from GCGC authentication"
echo ""
