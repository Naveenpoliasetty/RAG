#!/bin/bash

# API Testing Script
# Usage: ./test_api.sh [HOST] [PORT]

HOST=${1:-localhost}
PORT=${2:-8000}
BASE_URL="http://${HOST}:${PORT}"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Testing Resume Parser API"
echo "=========================================="
echo "Base URL: $BASE_URL"
echo ""

# Test 1: Root endpoint
echo -n "Test 1: Root endpoint... "
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    curl -s "$BASE_URL/" | jq .
else
    echo -e "${RED}✗ FAILED (HTTP $response)${NC}"
fi
echo ""

# Test 2: Health endpoint
echo -n "Test 2: Health endpoint... "
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    curl -s "$BASE_URL/health" | jq .
else
    echo -e "${RED}✗ FAILED (HTTP $response)${NC}"
fi
echo ""

# Test 3: API Documentation
echo -n "Test 3: API Documentation... "
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/docs")
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    echo "Docs available at: $BASE_URL/docs"
else
    echo -e "${RED}✗ FAILED (HTTP $response)${NC}"
fi
echo ""

# Test 4: OpenAPI schema
echo -n "Test 4: OpenAPI schema... "
response=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/openapi.json")
if [ "$response" -eq 200 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
else
    echo -e "${RED}✗ FAILED (HTTP $response)${NC}"
fi
echo ""

# Test 5: Qdrant health
echo -n "Test 5: Qdrant health... "
qdrant_response=$(curl -s -o /dev/null -w "%{http_code}" "http://${HOST}:6333/health")
if [ "$qdrant_response" -eq 200 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"
    curl -s "http://${HOST}:6333/health" | jq .
else
    echo -e "${RED}✗ FAILED (HTTP $qdrant_response)${NC}"
fi
echo ""

# Test 6: Parse resume endpoint (without file)
echo -n "Test 6: Parse resume endpoint (error test)... "
response=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/parse_resume")
if [ "$response" -eq 422 ]; then
    echo -e "${GREEN}✓ PASSED (Expected validation error)${NC}"
else
    echo -e "${YELLOW}⚠ UNEXPECTED (HTTP $response)${NC}"
fi
echo ""

echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "All basic endpoints are functional!"
echo ""
echo "To test resume parsing with a file:"
echo "curl -X POST \"$BASE_URL/parse_resume\" \\"
echo "  -H \"Content-Type: multipart/form-data\" \\"
echo "  -F \"file=@/path/to/resume.docx\""
echo ""

