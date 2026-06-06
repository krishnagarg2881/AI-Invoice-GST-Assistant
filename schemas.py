from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime

# --- Invoice Items ---
class InvoiceItemBase(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None
    gst_rate: Optional[float] = 0.0

class InvoiceItemCreate(InvoiceItemBase):
    pass

class InvoiceItemResponse(InvoiceItemBase):
    id: int
    invoice_id: int

    class Config:
        from_attributes = True

# --- Invoices ---
class InvoiceBase(BaseModel):
    vendor_name: Optional[str] = None
    invoice_date: Optional[date] = None
    invoice_number: Optional[str] = None
    gstin_vendor: Optional[str] = None
    gstin_recipient: Optional[str] = None
    taxable_amount: float = 0.0
    cgst: float = 0.0
    sgst_utgst: float = 0.0
    igst: float = 0.0
    total_amount: float = 0.0
    expense_category: str = "Others"

class InvoiceCreate(InvoiceBase):
    file_name: str
    file_path: str
    status: str = "pending"

class InvoiceUpdate(BaseModel):
    vendor_name: Optional[str] = None
    invoice_date: Optional[date] = None
    invoice_number: Optional[str] = None
    gstin_vendor: Optional[str] = None
    gstin_recipient: Optional[str] = None
    taxable_amount: Optional[float] = None
    cgst: Optional[float] = None
    sgst_utgst: Optional[float] = None
    igst: Optional[float] = None
    total_amount: Optional[float] = None
    expense_category: Optional[str] = None
    status: Optional[str] = None

class InvoiceResponse(InvoiceBase):
    id: int
    file_name: str
    file_path: str
    status: str
    raw_ocr_text: Optional[str] = None
    created_at: datetime
    items: List[InvoiceItemResponse] = []

    class Config:
        from_attributes = True

# --- AI Extraction Schema ---
class ExtractedInvoiceItem(BaseModel):
    description: str = Field(description="Description of the item or service")
    quantity: Optional[float] = Field(None, description="Quantity purchased")
    unit_price: Optional[float] = Field(None, description="Unit price of the item")
    amount: Optional[float] = Field(None, description="Total amount for this item before tax")
    gst_rate: Optional[float] = Field(0.0, description="GST rate applied to this item in percent (e.g. 18.0 for 18%)")

class ExtractedInvoice(BaseModel):
    vendor_name: Optional[str] = Field(None, description="Name of the supplier / vendor company")
    invoice_date: Optional[str] = Field(None, description="Date of the invoice in YYYY-MM-DD format")
    invoice_number: Optional[str] = Field(None, description="Invoice number or bill reference number")
    gstin_vendor: Optional[str] = Field(None, description="15-character GSTIN of the vendor/supplier in India")
    gstin_recipient: Optional[str] = Field(None, description="15-character GSTIN of the customer/recipient (our business) in India")
    taxable_amount: float = Field(0.0, description="Total taxable amount before GST charges")
    cgst: float = Field(0.0, description="Total Central GST amount")
    sgst_utgst: float = Field(0.0, description="Total State GST / Union Territory GST amount")
    igst: float = Field(0.0, description="Total Integrated GST amount")
    total_amount: float = Field(0.0, description="Grand total amount of the invoice (including all taxes)")
    expense_category: str = Field(
        "Others", 
        description="Categorize the expense into one of: 'Transport', 'Inventory', 'Utilities', 'Office Supplies', 'Meals & Entertainment', 'Rent', 'Salaries', 'Others'"
    )
    items: List[ExtractedInvoiceItem] = Field(default=[], description="List of line items in the invoice")

# --- Chat History ---
class ChatMessageBase(BaseModel):
    role: str
    content: str

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessageResponse(ChatMessageBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# --- Settings ---
class SettingsResponse(BaseModel):
    database_url: str
    gemini_api_key_configured: bool
    openai_api_key_configured: bool
    business_gstin: Optional[str] = None

class SettingsUpdate(BaseModel):
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    business_gstin: Optional[str] = None
