"""
SMS Parser Service
Extracts transaction data from SMS notifications
Supports: PhonePe, GPay, Bank SMS, Credit Card SMS
"""
import re
from datetime import datetime
from typing import Dict, Optional, Tuple


class SMSParser:
    """Parse transaction SMS and extract structured data"""
    
    # Merchant to category mapping
    MERCHANT_CATEGORIES = {
        # Food
        "zomato": "Food",
        "swiggy": "Food",
        "uber eats": "Food",
        "dominos": "Food",
        "pizza hut": "Food",
        "mcdonald": "Food",
        "kfc": "Food",
        
        # Travel
        "uber": "Travel",
        "ola": "Travel",
        "rapido": "Travel",
        "irctc": "Travel",
        "makemytrip": "Travel",
        "goibibo": "Travel",
        
        # Shopping
        "amazon": "Shopping",
        "flipkart": "Shopping",
        "myntra": "Shopping",
        "nykaa": "Shopping",
        "meesho": "Shopping",
        
        # Bills
        "electricity": "Bills",
        "gas": "Bills",
        "water": "Bills",
        "bsnl": "Bills",
        "airtel": "Bills",
        "jio": "Bills",
        "vodafone": "Bills",
        
        # Entertainment
        "netflix": "Entertainment",
        "hotstar": "Entertainment",
        "prime": "Entertainment",
        "spotify": "Entertainment",
        
        # Medicine
        "pharmacy": "Medicine",
        "apollo": "Medicine",
        "1mg": "Medicine",
        "netmeds": "Medicine",
    }
    
    @staticmethod
    def parse_sms(sms_body: str, sender: str = "") -> Optional[Dict]:
        """
        Parse SMS and extract transaction details
        Returns: {
            "amount": float,
            "transaction_type": "debit" | "credit",
            "merchant": str,
            "category_guess": str,
            "transaction_date": datetime,
            "account_number": str (last 4 digits),
            "reference_number": str
        } or None if not a transaction SMS
        """
        sms_lower = sms_body.lower()
        
        # Check if it's a transaction SMS
        if not SMSParser._is_transaction_sms(sms_lower):
            return None
        
        # Extract amount
        amount = SMSParser._extract_amount(sms_body)
        if not amount:
            return None
        
        # Determine transaction type
        transaction_type = SMSParser._detect_transaction_type(sms_lower)
        
        # Extract merchant
        merchant = SMSParser._extract_merchant(sms_body, sms_lower)
        
        # Guess category
        category_guess = SMSParser._guess_category(merchant, sms_lower)
        
        # Extract date
        transaction_date = SMSParser._extract_date(sms_body) or datetime.utcnow()
        
        # Extract account number (last 4 digits)
        account_number = SMSParser._extract_account_number(sms_body)
        
        # Extract reference number
        reference_number = SMSParser._extract_reference_number(sms_body)
        
        return {
            "amount": amount,
            "transaction_type": transaction_type,
            "merchant": merchant or "Unknown",
            "category_guess": category_guess or "Other",
            "transaction_date": transaction_date,
            "account_number": account_number,
            "reference_number": reference_number
        }
    
    @staticmethod
    def _is_transaction_sms(sms_lower: str) -> bool:
        """Check if SMS is a transaction notification"""
        transaction_keywords = [
            "debited", "credited", "paid", "received",
            "rs.", "rs ", "inr", "₹",
            "transaction", "payment", "upi",
            "balance", "account"
        ]
        
        # Must have amount indicator
        has_amount = bool(re.search(r'[₹]?\s*(\d+[.,]\d{2}|\d+)', sms_lower))
        
        # Must have transaction keyword
        has_keyword = any(keyword in sms_lower for keyword in transaction_keywords)
        
        return has_amount and has_keyword
    
    @staticmethod
    def _extract_amount(sms_body: str) -> Optional[float]:
        """Extract amount from SMS"""
        # Patterns: ₹299, Rs. 299, INR 299, 299.00, etc.
        patterns = [
            r'[₹]?\s*(\d+[.,]\d{2})',  # ₹299.00 or 299.00
            r'[₹]?\s*(\d+)',  # ₹299 or 299
            r'rs\.?\s*(\d+[.,]?\d*)',  # Rs. 299 or Rs 299
            r'inr\s*(\d+[.,]?\d*)',  # INR 299
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sms_body, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        
        return None
    
    @staticmethod
    def _detect_transaction_type(sms_lower: str) -> str:
        """Detect if transaction is debit or credit"""
        credit_keywords = ["credited", "received", "deposit", "refund"]
        debit_keywords = ["debited", "paid", "spent", "purchase", "withdrawal"]
        
        if any(keyword in sms_lower for keyword in credit_keywords):
            return "credit"
        elif any(keyword in sms_lower for keyword in debit_keywords):
            return "debit"
        
        # Default: check context
        if "from" in sms_lower or "received" in sms_lower:
            return "credit"
        else:
            return "debit"
    
    @staticmethod
    def _extract_merchant(sms_body: str, sms_lower: str) -> Optional[str]:
        """Extract merchant name from SMS"""
        # Common merchant patterns
        merchants = [
            "phonepe", "gpay", "paytm", "amazon pay",
            "zomato", "swiggy", "uber", "ola",
            "amazon", "flipkart", "myntra"
        ]
        
        for merchant in merchants:
            if merchant in sms_lower:
                return merchant.title()
        
        # Try to extract from "paid to" or "at" patterns
        patterns = [
            r'paid\s+to\s+([A-Za-z\s]+)',
            r'at\s+([A-Za-z\s]+)',
            r'to\s+([A-Za-z\s]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sms_body, re.IGNORECASE)
            if match:
                merchant = match.group(1).strip()
                if len(merchant) < 30:  # Reasonable merchant name length
                    return merchant
        
        return None
    
    @staticmethod
    def _guess_category(merchant: Optional[str], sms_lower: str) -> Optional[str]:
        """Guess category based on merchant or SMS content"""
        if merchant:
            merchant_lower = merchant.lower()
            for key, category in SMSParser.MERCHANT_CATEGORIES.items():
                if key in merchant_lower:
                    return category
        
        # Fallback: check SMS content for category hints
        if any(word in sms_lower for word in ["food", "restaurant", "order"]):
            return "Food"
        elif any(word in sms_lower for word in ["taxi", "cab", "ride", "travel"]):
            return "Travel"
        elif any(word in sms_lower for word in ["bill", "electricity", "gas", "water"]):
            return "Bills"
        elif any(word in sms_lower for word in ["medicine", "pharmacy", "medical"]):
            return "Medicine"
        
        return "Other"
    
    @staticmethod
    def _extract_date(sms_body: str) -> Optional[datetime]:
        """Extract transaction date from SMS"""
        # Common date patterns in Indian SMS
        patterns = [
            r'(\d{2}[/-]\d{2}[/-]\d{4})',  # DD/MM/YYYY
            r'(\d{2}[/-]\d{2}[/-]\d{2})',  # DD/MM/YY
            r'(\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4})',  # DD MMM YYYY
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sms_body, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Try parsing different formats
                    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y"]:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
                except:
                    continue
        
        return None
    
    @staticmethod
    def _extract_account_number(sms_body: str) -> Optional[str]:
        """Extract last 4 digits of account number"""
        # Pattern: "A/c **1234" or "Account ending 1234"
        patterns = [
            r'a/c\s*\*+\s*(\d{4})',
            r'account\s+ending\s+(\d{4})',
            r'ending\s+(\d{4})',
            r'\*\*(\d{4})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sms_body, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def _extract_reference_number(sms_body: str) -> Optional[str]:
        """Extract transaction reference number"""
        # Pattern: "Ref No: ABC123" or "Txn ID: 123456"
        patterns = [
            r'ref\s*(?:no|number)[:.]?\s*([A-Z0-9]+)',
            r'txn\s*(?:id|ref)[:.]?\s*([A-Z0-9]+)',
            r'reference[:.]?\s*([A-Z0-9]+)',
            r'upi\s*ref\s*([A-Z0-9]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, sms_body, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def generate_sms_hash(amount: float, merchant: str, date: datetime) -> str:
        """Generate hash for duplicate detection"""
        import hashlib
        hash_string = f"{amount}_{merchant}_{date.strftime('%Y-%m-%d %H:%M')}"
        return hashlib.md5(hash_string.encode()).hexdigest()

