# SMS Parsing Test Cases

## Test the SMS Parser

Use the `/api/detected/parse-sms` endpoint to test parsing:

### Example 1: PhonePe Transaction
```bash
curl -X POST "http://localhost:8000/api/detected/parse-sms" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sms_body": "₹299 debited from A/c **1234 for payment to ZOMATO. UPI:123456789. Bal: ₹5,000",
    "sender": "VK-PHONEP"
  }'
```

Expected Response:
```json
{
  "valid": true,
  "data": {
    "amount": 299.0,
    "transaction_type": "debit",
    "merchant": "Zomato",
    "category_guess": "Food",
    "transaction_date": "2024-01-15T10:30:00",
    "account_number": "1234",
    "reference_number": "123456789"
  }
}
```

### Example 2: Bank Credit
```bash
curl -X POST "http://localhost:8000/api/detected/parse-sms" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sms_body": "INR 50,000 credited to A/c **5678 from SALARY. Bal: ₹1,00,000",
    "sender": "HDFCBK"
  }'
```

### Example 3: GPay Expense
```bash
curl -X POST "http://localhost:8000/api/detected/parse-sms" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sms_body": "You paid ₹1,200 to UBER via Google Pay. Ref: GP123456",
    "sender": "GOOGLEPAY"
  }'
```

---

## Test Scenarios

### ✅ Should Parse:
- PhonePe transactions
- GPay transactions
- Bank debit/credit SMS
- UPI transactions
- Credit card transactions

### ❌ Should NOT Parse:
- OTP messages
- Promotional SMS
- Balance inquiry (without transaction)
- General notifications

---

## Validation Rules

1. **Must have amount** - SMS without amount is rejected
2. **Must have transaction keyword** - "debited", "credited", "paid", etc.
3. **Duplicate detection** - Same amount+merchant+time within 5 minutes = duplicate
4. **Valid date** - If date not found, uses current time

