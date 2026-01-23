#!/bin/bash
# Test deployed RegAtlas service

URL="https://reg-atlas.onrender.com"

echo "Testing RegAtlas deployment at $URL"
echo "======================================"
echo ""

echo "1. Health Check:"
curl -s "$URL/" | python3 -m json.tool || echo "Failed"
echo ""

echo "2. Stats Endpoint:"
curl -s "$URL/stats" | python3 -m json.tool || echo "Failed"
echo ""

echo "3. API Docs:"
echo "   Visit: $URL/docs"
echo ""

echo "Done! If all tests passed, RegAtlas is live! 🚀"
